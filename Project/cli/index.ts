import {
  createCliRenderer,
  Box,
  Text,
  ScrollBoxRenderable,
  TextRenderable,
  InputRenderable,
  InputRenderableEvents,
} from "@opentui/core";
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  unlinkSync,
} from "fs";
import { join } from "path";
import os from "os";

interface Auction {
  id: number;
  name: string;
  status: string;
  is_registered: boolean;
}

interface Bid {
  id: number;
  item_id: number;
  amount: string;
  item: {
    id: number;
    name: string;
    current_bid: string;
    current_bidder_id: number | null;
    auction: {
      id: number;
    };
  };
  bidder?: { id: number; name: string };
}

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
}

interface ChatMessage {
  type: "command" | "response" | "prompt" | "info";
  content: string;
}

type AuthStep =
  | { type: "command" }
  | { type: "login"; step: "email" | "password" }
  | { type: "register"; step: "name" | "email" | "password" | "role" }
  | { type: "create-auction"; step: "name" | "ended-at" }
  | { type: "add-item"; step: "auction-id" | "name" | "opening-price" }
  | { type: "end-auction"; step: "auction-id" }
  | { type: "update-auction"; step: "auction-id" | "field" | "value" };

let chatMessages: ChatMessage[] = [];
let currentUser: User | null = null;
let authState: AuthStep = { type: "command" };
let loginData: { email?: string; password?: string } = {};
let registerData: {
  name?: string;
  email?: string;
  password?: string;
  role?: string;
} = {};
let createAuctionData: { name?: string; endedAt?: string } = {};
let addItemData: { auctionId?: string; name?: string; openingPrice?: string } =
  {};
let endAuctionData: { auctionId?: string } = {};
let updateAuctionData: { auctionId?: string; field?: string; value?: string } =
  {};

const url = process.env.SERVER_URL;

function getToken(): string | null {
  const tokenPath = join(os.homedir(), ".auction-cli", "token");
  if (existsSync(tokenPath)) {
    return readFileSync(tokenPath, "utf-8").trim();
  }
  return null;
}

function saveToken(token: string): void {
  const tokenPath = join(os.homedir(), ".auction-cli", "token");
  const tokenDir = join(os.homedir(), ".auction-cli");
  if (!existsSync(tokenDir)) {
    mkdirSync(tokenDir, { recursive: true });
  }
  writeFileSync(tokenPath, token, { mode: 0o600 });
}

function deleteToken(): void {
  const tokenPath = join(os.homedir(), ".auction-cli", "token");
  if (existsSync(tokenPath)) {
    unlinkSync(tokenPath);
  }
}

async function fetchCurrentUser(token: string): Promise<User | null> {
  try {
    console.log(`${url}/auth/me`);
    const response = await fetch(`${url}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) {
      return await response.json();
    }
  } catch (e) {
    console.error("Failed to fetch user:", e);
  }
  return null;
}

async function fetchAuctions(token: string): Promise<Auction[]> {
  try {
    const response = await fetch(`${url}/auctions/get_auctions`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) return await response.json();
  } catch (e) {
    console.error("Failed to fetch auctions:", e);
  }
  return [];
}

async function fetchUserBids(token: string): Promise<Bid[]> {
  try {
    const response = await fetch(`${url}/customers/bids`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) {
      const bids: Bid[] = await response.json();
      const deduped = new Map<number, Bid>();
      for (const bid of bids) {
        const existing = deduped.get(bid.item_id);
        if (!existing || parseFloat(bid.amount) > parseFloat(existing.amount)) {
          deduped.set(bid.item_id, bid);
        }
      }
      return Array.from(deduped.values());
    }
  } catch (e) {
    console.error("Failed to fetch bids:", e);
  }
  return [];
}

async function apiLogin(
  email: string,
  password: string,
): Promise<{ success: boolean; token?: string; error?: string }> {
  try {
    const params = new URLSearchParams();
    params.append("username", email);
    params.append("password", password);

    const response = await fetch(`${url}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params.toString(),
    });

    if (response.ok) {
      const data = await response.json();
      return { success: true, token: data.access_token };
    } else {
      return { success: false, error: "Invalid email or password" };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

async function apiRegister(
  name: string,
  email: string,
  password: string,
  role: string,
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch(`${url}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password, role }),
    });

    if (response.ok) {
      return { success: true };
    } else {
      const error = await response.json();
      return { success: false, error: error.detail || "Registration failed" };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

async function apiCreateAuction(
  token: string,
  name: string,
  endedAt?: string,
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const data: any = { name };
    if (endedAt) data.ended_at = endedAt;

    const response = await fetch(`${url}/managers/auctions/`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (response.ok) {
      const result = await response.json();
      return { success: true, data: result };
    } else {
      const error = await response.json();
      return {
        success: false,
        error: error.detail || "Failed to create auction",
      };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

async function apiAddItem(
  token: string,
  auctionId: string,
  name: string,
  openingPrice: string,
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const response = await fetch(
      `${url}/managers/auctions/${auctionId}/items`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name,
          opening_price: parseFloat(openingPrice),
          auction_id: parseInt(auctionId),
        }),
      },
    );

    if (response.ok) {
      const result = await response.json();
      return { success: true, data: result };
    } else {
      const error = await response.json();
      return { success: false, error: error.detail || "Failed to add item" };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

async function apiEndAuction(
  token: string,
  auctionId: string,
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const response = await fetch(`${url}/managers/auctions/${auctionId}/end`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.ok) {
      const result = await response.json();
      return { success: true, data: result };
    } else {
      const error = await response.json();
      return { success: false, error: error.detail || "Failed to end auction" };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

async function apiUpdateAuction(
  token: string,
  auctionId: string,
  field: string,
  value: string,
): Promise<{ success: boolean; data?: any; error?: string }> {
  try {
    const data: any = {};
    if (field === "name") data.name = value;
    else if (field === "status") data.status = value;
    else if (field === "ended_at") data.ended_at = value;

    const response = await fetch(`${url}/managers/auctions/${auctionId}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (response.ok) {
      const result = await response.json();
      return { success: true, data: result };
    } else {
      const error = await response.json();
      return {
        success: false,
        error: error.detail || "Failed to update auction",
      };
    }
  } catch (e) {
    return { success: false, error: `Connection error: ${e}` };
  }
}

function formatUpdateAuctionFields(): string {
  return `Available fields: name, status, ended_at
Enter the field you want to update:`;
}

async function main() {
  const token = getToken();
  if (token) {
    currentUser = await fetchCurrentUser(token);
  }

  const initialHelp: ChatMessage = {
    type: "response",
    content:
      "Welcome to Auction House CLI!\n\nCommands:\n  register              Register a new user\n  login                 Login to your account\n  logout                Logout and exit\n  whoami                Show current user\n  list-auctions         List all auctions\n  view-auction <id>     View auction details\n  register-auction <id> Register for auction\n  place-bid <aid> <iid> <amt> Place a bid\n  my-bids               View your bids\n\nManager Commands:\n  create-auction        Create a new auction\n  add-item              Add item to auction\n  end-auction           End an auction\n  update-auction        Update auction details",
  };
  chatMessages.push(initialHelp);

  let auctions: Auction[] = [];
  let bids: Bid[] = [];

  if (!token || !currentUser) {
    auctions = [
      {
        id: 1,
        name: "Spring Art Collection",
        status: "active",
        is_registered: false,
      },
      {
        id: 2,
        name: "Vintage Electronics Auction",
        status: "active",
        is_registered: false,
      },
    ];
  } else {
    [auctions, bids] = await Promise.all([
      fetchAuctions(token),
      fetchUserBids(token),
    ]);
  }

  const registeredAuctions = auctions.filter((a) => a.is_registered);
  const userId = currentUser?.id || null;

  const renderer = await createCliRenderer({ exitOnCtrlC: true });

  const scrollBox = new ScrollBoxRenderable(renderer, {
    id: "chat-scroll",
    border: false,
    padding: 0.5,
    stickyScroll: true,
    stickyStart: "bottom",
  });

  let msgCounter = 0;
  function appendMessage(msg: ChatMessage) {
    const node = new TextRenderable(renderer, {
      id: `msg-${msgCounter++}`,
      content: msg.content,
      flexShrink: 0,
    });
    scrollBox.add(node);
  }

  for (const msg of chatMessages) {
    appendMessage(msg);
  }

  const statusText = currentUser
    ? `Status: Logged in as ${currentUser.name}`
    : "Status: Guest";
  const statusMsg: ChatMessage = { type: "info", content: statusText };
  chatMessages.push(statusMsg);
  appendMessage(statusMsg);

  const rightPaneStatusText = new TextRenderable(renderer, {
    id: "status",
    content: statusText,
    bold: true,
    flexShrink: 0,
  });

  let inputField: InputRenderable;

  let rightPaneAuctionsText: TextRenderable[] = [];
  let rightPaneBidsText: TextRenderable[] = [];
  let rightPaneAuctionsPlaceholder: TextRenderable;
  let rightPaneBidsPlaceholder: TextRenderable;
  let rightPaneContainer: any;

  const updateRightPane = async () => {
    const newToken = getToken();
    if (!newToken || !currentUser) {
      rightPaneStatusText.content = "Status: Guest";
      rightPaneAuctionsText.forEach((el) => (el.content = ""));
      rightPaneBidsText.forEach((el) => (el.content = ""));
      rightPaneAuctionsPlaceholder.content = "No registered auctions";
      rightPaneAuctionsPlaceholder.visible = true;
      rightPaneBidsPlaceholder.content = "No bids placed";
      rightPaneBidsPlaceholder.visible = true;
      return;
    }

    const [newAuctions, newBids] = await Promise.all([
      fetchAuctions(newToken),
      fetchUserBids(newToken),
    ]);
    rightPaneStatusText.content = `Status: ${currentUser.name}`;

    const registered = newAuctions.filter((a: Auction) => a.is_registered);

    rightPaneAuctionsText.forEach((el) => (el.content = ""));
    rightPaneAuctionsPlaceholder.visible = registered.length === 0;
    rightPaneAuctionsPlaceholder.content = "No registered auctions";

    for (
      let i = 0;
      i < registered.length && i < rightPaneAuctionsText.length;
      i++
    ) {
      rightPaneAuctionsText[i].content =
        `• ${registered[i].name} (${registered[i].status})`;
    }

    rightPaneBidsText.forEach((el) => (el.content = ""));
    rightPaneBidsPlaceholder.visible = newBids.length === 0;
    rightPaneBidsPlaceholder.content = "No bids placed";

    const userId = currentUser?.id || null;
    for (let i = 0; i < newBids.length && i < rightPaneBidsText.length; i++) {
      const bid = newBids[i];
      if (!bid) continue;
      const isWinning = bid.item.current_bidder_id === userId;
      if (isWinning) {
        rightPaneBidsText[i].content =
          `• ${bid.item.name} (Item: ${bid.item.id}, Auc: ${bid.item.auction.id}) - $${bid.item.current_bid} (You)`;
        rightPaneBidsText[i].fg = "#00FF00";
      } else {
        rightPaneBidsText[i].content =
          `• ${bid.item.name} (Item: ${bid.item.id}, Auc: ${bid.item.auction.id}) - Your Bid: $${bid.amount} | Highest: $${bid.item.current_bid}`;
        rightPaneBidsText[i].fg = undefined;
      }
    }
  };

  const processCommand = async (cmd: string): Promise<ChatMessage> => {
    const parts = cmd.trim().split(/\s+/);
    const command = parts[0].toLowerCase();
    const args = parts.slice(1);

    const token = getToken();

    if (command === "login") {
      authState = { type: "login", step: "email" };
      return { type: "prompt", content: "Enter email:" };
    }

    if (command === "register") {
      authState = { type: "register", step: "name" };
      return { type: "prompt", content: "Enter name:" };
    }

    if (authState.type !== "command") {
      if (authState.type === "login") {
        if (authState.step === "email") {
          loginData.email = cmd.trim();
          authState = { type: "login", step: "password" };
          return { type: "prompt", content: "Enter password:" };
        } else if (authState.step === "password") {
          loginData.password = cmd.trim();
          authState = { type: "command" };
          const result = await apiLogin(loginData.email!, loginData.password!);
          loginData = {};
          if (result.success && result.token) {
            saveToken(result.token);
            currentUser = await fetchCurrentUser(result.token);
            await updateRightPane();
            return {
              type: "response",
              content: `Logged in as ${currentUser?.email}`,
            };
          }
          return { type: "response", content: result.error || "Login failed" };
        }
      } else if (authState.type === "register") {
        if (authState.step === "name") {
          registerData.name = cmd.trim();
          authState = { type: "register", step: "email" };
          return { type: "prompt", content: "Enter email:" };
        } else if (authState.step === "email") {
          registerData.email = cmd.trim();
          authState = { type: "register", step: "password" };
          return { type: "prompt", content: "Enter password:" };
        } else if (authState.step === "password") {
          registerData.password = cmd.trim();
          authState = { type: "register", step: "role" };
          return { type: "prompt", content: "Enter role (customer/manager):" };
        } else if (authState.step === "role") {
          const role = cmd.trim().toLowerCase();
          if (role !== "customer" && role !== "manager") {
            return {
              type: "prompt",
              content: "Invalid role. Please enter 'customer' or 'manager':",
            };
          }
          registerData.role = role;
          authState = { type: "command" };

          const result = await apiRegister(
            registerData.name!,
            registerData.email!,
            registerData.password!,
            registerData.role!,
          );
          registerData = {};

          if (result.success) {
            return {
              type: "response",
              content: "Registration successful! You can now login.",
            };
          }
          return {
            type: "response",
            content: result.error || "Registration failed",
          };
        }
      } else if (authState.type === "create-auction") {
        if (authState.step === "name") {
          createAuctionData.name = cmd.trim();
          authState = { type: "create-auction", step: "ended-at" };
          return {
            type: "prompt",
            content:
              "Enter end date (YYYY-MM-DDTHH:MM:SS) or press Enter to skip:",
          };
        } else if (authState.step === "ended-at") {
          const endedAt = cmd.trim();
          if (endedAt) createAuctionData.endedAt = endedAt;
          authState = { type: "command" };
          const result = await apiCreateAuction(
            token!,
            createAuctionData.name!,
            createAuctionData.endedAt,
          );
          createAuctionData = {};
          if (result.success && result.data) {
            return {
              type: "response",
              content: `Auction created!\n  ID: ${result.data.id}\n  Name: ${result.data.name}\n  Status: ${result.data.status}`,
            };
          }
          return {
            type: "response",
            content: result.error || "Failed to create auction",
          };
        }
      } else if (authState.type === "add-item") {
        if (authState.step === "auction-id") {
          addItemData.auctionId = cmd.trim();
          authState = { type: "add-item", step: "name" };
          return { type: "prompt", content: "Enter item name:" };
        } else if (authState.step === "name") {
          addItemData.name = cmd.trim();
          authState = { type: "add-item", step: "opening-price" };
          return { type: "prompt", content: "Enter opening price:" };
        } else if (authState.step === "opening-price") {
          addItemData.openingPrice = cmd.trim();
          authState = { type: "command" };
          const result = await apiAddItem(
            token!,
            addItemData.auctionId!,
            addItemData.name!,
            addItemData.openingPrice!,
          );
          addItemData = {};
          if (result.success && result.data) {
            return {
              type: "response",
              content: `Item added!\n  Item ID: ${result.data.id}\n  Name: ${result.data.name}\n  Opening Price: $${result.data.opening_price}`,
            };
          }
          return {
            type: "response",
            content: result.error || "Failed to add item",
          };
        }
      } else if (authState.type === "end-auction") {
        if (authState.step === "auction-id") {
          endAuctionData.auctionId = cmd.trim();
          authState = { type: "command" };
          const result = await apiEndAuction(token!, endAuctionData.auctionId!);
          endAuctionData = {};
          if (result.success && result.data) {
            await updateRightPane();
            return {
              type: "response",
              content: `Auction ended!\n  ID: ${result.data.id}\n  Name: ${result.data.name}\n  Status: ${result.data.status}`,
            };
          }
          return {
            type: "response",
            content: result.error || "Failed to end auction",
          };
        }
      } else if (authState.type === "update-auction") {
        if (authState.step === "auction-id") {
          updateAuctionData.auctionId = cmd.trim();
          authState = { type: "update-auction", step: "field" };
          return { type: "prompt", content: formatUpdateAuctionFields() };
        } else if (authState.step === "field") {
          const field = cmd.trim().toLowerCase();
          if (field !== "name" && field !== "status" && field !== "ended_at") {
            return {
              type: "prompt",
              content: `Invalid field. ${formatUpdateAuctionFields()}`,
            };
          }
          updateAuctionData.field = field;
          authState = { type: "update-auction", step: "value" };
          return { type: "prompt", content: `Enter new value for ${field}:` };
        } else if (authState.step === "value") {
          updateAuctionData.value = cmd.trim();
          authState = { type: "command" };
          const result = await apiUpdateAuction(
            token!,
            updateAuctionData.auctionId!,
            updateAuctionData.field!,
            updateAuctionData.value!,
          );
          updateAuctionData = {};
          if (result.success && result.data) {
            return {
              type: "response",
              content: `Auction updated!\n  ID: ${result.data.id}\n  Name: ${result.data.name}\n  Status: ${result.data.status}`,
            };
          }
          return {
            type: "response",
            content: result.error || "Failed to update auction",
          };
        }
      }
    }

    if (!token && command !== "help") {
      return {
        type: "response",
        content: "Not logged in. Use 'login' or 'register' first.",
      };
    }

    try {
      switch (command) {
        case "help":
          return chatMessages[0];

        case "whoami":
          if (!currentUser) {
            return { type: "response", content: "Not logged in" };
          }
          return {
            type: "response",
            content: `${currentUser.name} (${currentUser.email}) - ${currentUser.role}`,
          };

        case "logout":
          deleteToken();
          currentUser = null;
          await updateRightPane();
          return { type: "response", content: "Logged out successfully." };

        case "list-auctions": {
          const auctionList = await fetchAuctions(token!);
          if (!auctionList.length)
            return { type: "response", content: "No auctions found." };
          let result = "";
          for (const a of auctionList) {
            result += `  ${a.name} (ID: ${a.id}) - ${a.status}\n`;
          }
          return { type: "response", content: result };
        }

        case "register-auction": {
          const auctionId = parseInt(args[0]);
          if (isNaN(auctionId))
            return {
              type: "response",
              content: "Usage: register-auction <auction_id>",
            };
          const res = await fetch(`${url}/auctions/${auctionId}/register`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) {
            const err = await res.json();
            return {
              type: "response",
              content: err.detail || "Failed to register",
            };
          }
          await updateRightPane();
          return {
            type: "response",
            content: "Successfully registered for auction!",
          };
        }

        case "place-bid": {
          const auctionId = parseInt(args[0]);
          const itemId = parseInt(args[1]);
          const amount = parseFloat(args[2]);
          if (isNaN(auctionId) || isNaN(itemId) || isNaN(amount)) {
            return {
              type: "response",
              content: "Usage: place-bid <auction_id> <item_id> <amount>",
            };
          }
          const res = await fetch(`${url}/auctions/${auctionId}/bids`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ item_id: itemId, amount }),
          });
          if (!res.ok) {
            const err = await res.json();
            return {
              type: "response",
              content: err.detail || "Failed to place bid",
            };
          }
          await updateRightPane();
          return { type: "response", content: "Bid placed successfully!" };
        }

        case "my-bids": {
          const bidList = await fetchUserBids(token!);
          if (!bidList.length)
            return { type: "response", content: "No bids found." };
          let result = "Your Bids:\n";
          for (const bid of bidList) {
            result += `  ${bid.item.name} - $${bid.amount}\n`;
          }
          return { type: "response", content: result };
        }

        case "view-auction": {
          const auctionId = parseInt(args[0]);
          if (isNaN(auctionId))
            return {
              type: "response",
              content: "Usage: view-auction <auction_id>",
            };
          const res = await fetch(`${url}/auctions/${auctionId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok)
            return { type: "response", content: "Auction not found" };
          const auction = await res.json();
          let result = `Auction: ${auction.name}\nStatus: ${auction.status}\n`;
          if (auction.items?.length) {
            result += "Items:\n";
            for (const item of auction.items) {
              result += `  ${item.name} (ID: ${item.id}) - Current Bid: $${item.current_bid}\n`;
            }
          }
          return { type: "response", content: result };
        }

        case "create-auction": {
          if (currentUser?.role !== "manager") {
            return {
              type: "response",
              content: "You are not authorized to create auctions.",
            };
          }
          authState = { type: "create-auction", step: "name" };
          return { type: "prompt", content: "Enter auction name:" };
        }

        case "add-item": {
          if (currentUser?.role !== "manager") {
            return {
              type: "response",
              content: "You are not authorized to add items.",
            };
          }
          authState = { type: "add-item", step: "auction-id" };
          return { type: "prompt", content: "Enter auction ID:" };
        }

        case "end-auction": {
          if (currentUser?.role !== "manager") {
            return {
              type: "response",
              content: "You are not authorized to end auctions.",
            };
          }
          authState = { type: "end-auction", step: "auction-id" };
          return { type: "prompt", content: "Enter auction ID to end:" };
        }

        case "update-auction": {
          if (currentUser?.role !== "manager") {
            return {
              type: "response",
              content: "You are not authorized to update auctions.",
            };
          }
          authState = { type: "update-auction", step: "auction-id" };
          return { type: "prompt", content: "Enter auction ID to update:" };
        }

        default:
          return {
            type: "response",
            content: `Unknown command: ${command}. Type 'help' for available commands.`,
          };
      }
    } catch (e) {
      return { type: "response", content: `Error: ${e}` };
    }
  };

  inputField = new InputRenderable(renderer, {
    id: "cmd-input",
    placeholder: "Type command...",
    width: "100%",
  });

  inputField.on(InputRenderableEvents.CHANGE, async (value: string) => {
    const cmd = value.trim();
    if (!cmd) return;

    inputField.value = "";

    const inAuthFlow = authState.type !== "command";

    if (!inAuthFlow) {
      const cmdMsg: ChatMessage = { type: "command", content: cmd };
      chatMessages.push(cmdMsg);
      appendMessage(cmdMsg);
    }

    const response = await processCommand(cmd);

    chatMessages.push(response);
    appendMessage(response);

    if (authState.type === "command") {
      inputField.placeholder = "Type command...";
      inputField.focus();
    } else {
      inputField.focus();
    }
  });

  inputField.focus();

  const leftPane = Box(
    {
      flex: 1,
      border: true,
      borderStyle: "rounded",
      padding: 0,
      flexDirection: "column",
    },
    scrollBox,
    Box({ id: "input-area", padding: 1 }, inputField),
  );

  rightPaneAuctionsText = [];
  rightPaneBidsText = [];

  const rightPaneHeader: any[] = [
    rightPaneStatusText,
    Text({ content: "" }),
    Text({ content: "My Registered Auctions", bold: true }),
    Text({ content: "─".repeat(30) }),
  ];

  rightPaneAuctionsPlaceholder = new TextRenderable(renderer, {
    content: registeredAuctions.length === 0 ? "No registered auctions" : "",
    flexShrink: 0,
  });
  rightPaneAuctionsPlaceholder.visible = registeredAuctions.length === 0;

  for (let i = 0; i < Math.max(registeredAuctions.length, 5); i++) {
    const t = new TextRenderable(renderer, {
      content:
        i < registeredAuctions.length
          ? `• ${registeredAuctions[i].name} (${registeredAuctions[i].status})`
          : "",
      flexShrink: 0,
    });
    t.visible = i < registeredAuctions.length;
    rightPaneAuctionsText.push(t);
  }

  const rightPaneBidsHeader: any[] = [
    Text({ content: "" }),
    Text({ content: "My Bids", bold: true }),
    Text({ content: "─".repeat(30) }),
  ];

  rightPaneBidsPlaceholder = new TextRenderable(renderer, {
    content: bids.length === 0 ? "No bids placed" : "",
    flexShrink: 0,
  });
  rightPaneBidsPlaceholder.visible = bids.length === 0;

  for (let i = 0; i < Math.max(bids.length, 5); i++) {
    const bid = bids[i];
    const isWinning = bid && bid.item.current_bidder_id === userId;
    let content: string;
    let fg: string | undefined;
    if (bid) {
      if (isWinning) {
        content = `• ${bid.item.name} (Item: ${bid.item.id}, Auc: ${bid.item.auction.id}) - $${bid.item.current_bid} (You)`;
        fg = "#00FF00";
      } else {
        content = `• ${bid.item.name} (Item: ${bid.item.id}, Auc: ${bid.item.auction.id}) - Your Bid: $${bid.amount} | Highest: $${bid.item.current_bid}`;
        fg = undefined;
      }
    } else {
      content = "";
      fg = undefined;
    }
    const t = new TextRenderable(renderer, {
      content,
      fg,
      flexShrink: 0,
    });
    t.visible = i < bids.length;
    rightPaneBidsText.push(t);
  }

  rightPaneContainer = Box(
    {
      flex: 1,
      border: true,
      borderStyle: "rounded",
      padding: 1,
      flexDirection: "column",
      gap: 1,
    },
    ...rightPaneHeader,
    rightPaneAuctionsPlaceholder,
    ...rightPaneAuctionsText,
    ...rightPaneBidsHeader,
    rightPaneBidsPlaceholder,
    ...rightPaneBidsText,
  );

  const mainBox = Box(
    { flexDirection: "row", width: "100%", height: "100%" },
    leftPane,
    rightPaneContainer,
  );

  renderer.root.add(mainBox);

  setInterval(updateRightPane, 2500);
}

main();
