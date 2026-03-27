import ollama
import os
import warnings
from sklearn.metrics.pairwise import cosine_similarity
from statsmodels.tsa.statespace.sarimax import SARIMAX
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from database import get_db, Bid, AuctionItem, Auction
from schemas import (
    PricePredictionRequest,
    PricePredictionResponse,
    ForecastItem,
    BidPredictionItem,
    BidPredictionsResponse,
)
import auth
from contextlib import asynccontextmanager

warnings.filterwarnings("ignore")

router = APIRouter()

_predictor_instance = None
_csv_mtime = None


class PricePredictor:
    _instance = None

    def __new__(cls, csv_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, csv_path: str = None):
        if hasattr(self, "_initialized") and self._initialized:
            return

        if csv_path is None:
            csv_path = "/Users/rachitdas/Desktop/csci-6234/Project/api/output.csv"

        self._csv_path = csv_path
        self._csv_mtime = os.path.getmtime(csv_path)
        self.df = pd.read_csv(csv_path)

        self._price_cols = self._detect_price_columns()
        self._name_to_idx = {}
        self._embeddings_cached = {}
        self._build_name_index()
        self._initialized = True

    def _build_name_index(self):
        for idx, row in self.df.iterrows():
            name = str(row["product_name"]).lower().strip()
            if name not in self._name_to_idx:
                self._name_to_idx[name] = idx

    def check_csv_modified(self) -> bool:
        current_mtime = os.path.getmtime(self._csv_path)
        if current_mtime != self._csv_mtime:
            self._csv_mtime = current_mtime
            return True
        return False

    def reload_if_modified(self):
        if self.check_csv_modified():
            print("CSV file changed, reloading...")
            self.df = pd.read_csv(self._csv_path)
            self._name_to_idx = {}
            self._embeddings_cached = {}
            self._build_name_index()
            _prediction_cache.clear()
            print("Cache invalidated due to CSV change")

    def _detect_price_columns(self) -> list[str]:
        non_price = {"product_name"}
        date_cols = [c for c in self.df.columns if c not in non_price]
        if not date_cols:
            raise ValueError("No date columns found in the CSV.")
        return sorted(date_cols)

    def _get_embedding(self, text: str) -> np.ndarray:
        response = ollama.embed(model="nomic-embed-text:latest", input=text)
        vec = np.array(response["embeddings"][0], dtype=np.float32)
        return vec / (np.linalg.norm(vec) + 1e-10)

    def _get_embeddings_batch(self, texts: list[str]) -> dict[str, np.ndarray]:
        if not texts:
            return {}
        
        response = ollama.embed(model="nomic-embed-text:latest", input=texts)
        embeddings = response["embeddings"]
        
        result = {}
        for text, emb in zip(texts, embeddings):
            vec = np.array(emb, dtype=np.float32)
            result[text.lower().strip()] = vec / (np.linalg.norm(vec) + 1e-10)
        return result

    def _get_or_cache_embedding(self, name: str) -> np.ndarray:
        key = name.lower().strip()
        if key not in self._embeddings_cached:
            self._embeddings_cached[key] = self._get_embedding(name)
        return self._embeddings_cached[key]

    def cache_all_embeddings(self, batch_size: int = 50):
        if len(self._embeddings_cached) >= len(self._name_to_idx):
            print(f"All embeddings already cached ({len(self._embeddings_cached)} items)")
            return
        
        print(f"Caching embeddings for {len(self._name_to_idx)} unique items...")
        unique_names = list(self._name_to_idx.keys())
        
        for i in range(0, len(unique_names), batch_size):
            batch = unique_names[i:i+batch_size]
            uncached = [n for n in batch if n not in self._embeddings_cached]
            if uncached:
                batch_embs = self._get_embeddings_batch(uncached)
                self._embeddings_cached.update(batch_embs)
            if (i + batch_size) % 500 == 0 or i + batch_size >= len(unique_names):
                print(f"  Cached {min(i + batch_size, len(unique_names))}/{len(unique_names)} items")
        
        print(f"Done caching {len(self._embeddings_cached)} embeddings")

    def match_score(self, name1: str, name2: str) -> float:
        emb1 = self._get_or_cache_embedding(name1).reshape(1, -1)
        emb2 = self._get_or_cache_embedding(name2).reshape(1, -1)
        score = cosine_similarity(emb1, emb2)[0][0]
        return float(score)

    def find_best_match(self, item: str) -> dict:
        query_emb = self._get_or_cache_embedding(item).reshape(1, -1)
        
        unique_names = list(self._name_to_idx.keys())
        names_to_indices = list(self._name_to_idx.keys())
        
        if len(self._embeddings_cached) < len(self._name_to_idx):
            uncached = [n for n in names_to_indices if n not in self._embeddings_cached]
            for i in range(0, len(uncached), 50):
                batch = uncached[i:i+50]
                batch_embs = self._get_embeddings_batch(batch)
                self._embeddings_cached.update(batch_embs)
        
        embeddings_matrix = np.array([
            self._embeddings_cached[n] for n in names_to_indices
        ])
        
        scores = cosine_similarity(query_emb, embeddings_matrix)[0]
        best_idx = int(np.argmax(scores))
        
        best_name = names_to_indices[best_idx]
        best_row = self.df.iloc[self._name_to_idx[best_name]]

        return {
            "best_match_name": best_row["product_name"],
            "best_match_score": float(scores[best_idx]),
            "best_match_index": self._name_to_idx[best_name],
            "best_match_row": best_row.to_dict(),
            "all_scores": {},
        }

    def predict_price(
        self,
        item: str,
        steps: int = 7,
        order: tuple = (1, 1, 1),
        seasonal_order: tuple = (1, 1, 1, 7),
    ) -> dict:
        match_result = self.find_best_match(item)
        best_name = match_result["best_match_name"]
        best_score = match_result["best_match_score"]
        best_idx = match_result["best_match_index"]

        date_to_avg_prices = {}
        for col in self._price_cols:
            parts = col.rsplit(';', 1)
            if len(parts) == 2:
                date_part = parts[0]
                if date_part not in date_to_avg_prices:
                    date_to_avg_prices[date_part] = []
                date_to_avg_prices[date_part].append(float(self.df.iloc[best_idx][col]))

        sorted_dates = sorted(date_to_avg_prices.keys())
        raw_prices = [sum(date_to_avg_prices[d]) / len(date_to_avg_prices[d]) for d in sorted_dates]
        
        price_series = pd.Series(
            raw_prices,
            index=pd.to_datetime(sorted_dates),
        )
        price_series.index.freq = pd.infer_freq(price_series.index)

        model = SARIMAX(
            price_series,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit_result = model.fit(disp=False)

        forecast_obj = fit_result.get_forecast(steps=steps)
        forecast_mean = forecast_obj.predicted_mean
        conf_int = forecast_obj.conf_int()

        last_date = price_series.index[-1]
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1), periods=steps, freq="D"
        )

        forecast_df = pd.DataFrame(
            {
                "date": future_dates.strftime("%Y-%m-%d"),
                "predicted_price": forecast_mean.values.round(4),
                "lower_95": conf_int.iloc[:, 0].values.round(4),
                "upper_95": conf_int.iloc[:, 1].values.round(4),
            }
        )

        return {
            "matched_item": best_name,
            "similarity_score": best_score,
            "historical_prices": dict(
                zip(price_series.index.strftime("%Y-%m-%d"), price_series.values.tolist())
            ),
            "forecast": forecast_df.to_dict(orient="records"),
            "aic": fit_result.aic,
            "bic": fit_result.bic,
        }


_predictor_instance = None
_prediction_cache: dict = {}

def get_predictor(csv_path: str = None) -> PricePredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = PricePredictor(csv_path)
        print("Pre-caching all embeddings at startup...")
        _predictor_instance.cache_all_embeddings()
    return _predictor_instance

def _get_cached_prediction(item_name: str) -> dict:
    cache_key = item_name.lower().strip()
    if cache_key in _prediction_cache:
        return _prediction_cache[cache_key]
    return None

def _set_cached_prediction(item_name: str, data: dict):
    cache_key = item_name.lower().strip()
    _prediction_cache[cache_key] = data

def _clear_prediction_cache():
    global _prediction_cache
    _prediction_cache = {}


if __name__ == "__main__":
    predictor = PricePredictor(
        "/Users/rachitdas/Desktop/csci-6234/Project/api/output.csv"
    )

    score = predictor.match_score("wireless headphones", "bluetooth earbuds")
    print(f"Similarity: {score:.4f}\n")

    result = predictor.predict_price(
        item="Porcelian Vase Kings collection",
        steps=7,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 7),
    )
    print(result)


@router.post("/predict", response_model=PricePredictionResponse)
async def predict_price(request: PricePredictionRequest):
    predictor = get_predictor()
    predictor.reload_if_modified()
    result = predictor.predict_price(
        item=request.item,
        steps=request.steps,
        order=request.order,
        seasonal_order=request.seasonal_order,
    )
    result["forecast"] = [
        ForecastItem(**f) for f in result["forecast"]
    ]
    return result


@router.get("/items")
async def get_items():
    predictor = get_predictor()
    return {"items": predictor.df["product_name"].tolist()}


@router.get("/predictions/bids", response_model=BidPredictionsResponse)
async def get_bid_predictions(
    current_user = Depends(auth.get_current_customer),
    db: Session = Depends(get_db),
    steps: int = 3,
):
    bids = (
        db.query(Bid)
        .options(
            joinedload(Bid.item).joinedload(AuctionItem.auction)
        )
        .filter(Bid.bidder_id == current_user.id)
        .all()
    )

    seen_items = {}
    for bid in bids:
        item_id = bid.item_id
        if item_id not in seen_items:
            seen_items[item_id] = bid

    predictor = get_predictor()
    predictor.reload_if_modified()
    predictions = []

    for item_id, bid in seen_items.items():
        auction = bid.item.auction

        cached = _get_cached_prediction(bid.item.name)
        if cached:
            prediction_data = cached
        else:
            prediction_data = predictor.predict_price(
                item=bid.item.name,
                steps=steps,
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 7),
            )
            _set_cached_prediction(bid.item.name, prediction_data)

        prediction_data["forecast"] = [
            f if isinstance(f, ForecastItem) else ForecastItem(**f)
            for f in prediction_data["forecast"]
        ]

        is_winning = bid.item.current_bidder_id == current_user.id

        predictions.append(BidPredictionItem(
            item_id=bid.item_id,
            item_name=bid.item.name,
            auction_id=auction.id,
            current_bid=float(bid.item.current_bid),
            user_bid=float(bid.amount),
            is_winning=is_winning,
            prediction=PricePredictionResponse(**prediction_data),
        ))

    return BidPredictionsResponse(predictions=predictions)