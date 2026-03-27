import pandas as pd
import os

def deduplicate_prices(input_path: str = None, output_path: str = None):
    if input_path is None:
        input_path = "/Users/rachitdas/Desktop/csci-6234/Project/api/output_backup.csv"
    if output_path is None:
        output_path = "/Users/rachitdas/Desktop/csci-6234/Project/api/output.csv"
    
    print(f"Reading {input_path}...")
    df = pd.read_csv(input_path)
    
    print(f"Original shape: {df.shape}")
    print(f"Unique products: {df['product_name'].nunique()}")
    print(f"Price types: {df['price_type'].unique().tolist()}")
    
    date_cols = [c for c in df.columns if c not in ['product_name', 'price_type']]
    print(f"Date columns: {len(date_cols)}")
    
    print("\nPivoting data...")
    pivoted = df.pivot(index='product_name', columns='price_type', values=date_cols)
    
    print("Flattening column names...")
    new_columns = []
    for date_col in date_cols:
        for price_type in ['start', 'end']:
            new_columns.append(f"{date_col};{price_type}")
    
    pivoted.columns = new_columns
    pivoted = pivoted.reset_index()
    
    print(f"New shape: {pivoted.shape}")
    print(f"New columns: {len(pivoted.columns)}")
    
    print(f"\nWriting deduplicated data to {output_path}...")
    pivoted.to_csv(output_path, index=False)
    
    print("\nDone!")
    print(f"  - Original: {len(df)} rows")
    print(f"  - Deduplicated: {len(pivoted)} rows")
    print(f"  - New columns: {len(pivoted.columns)}")
    
    return pivoted

if __name__ == "__main__":
    result = deduplicate_prices()
    print("\nFirst 5 products:")
    print(result['product_name'].head().tolist())
    
    print("\nSample column names:")
    print(result.columns[1:6].tolist())
