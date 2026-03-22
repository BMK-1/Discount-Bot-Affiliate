# 🤖 Amazon & Flipkart Affiliate Discount Bot

Fully automated Telegram bot that posts the **best deals from Amazon India & Flipkart** to your channel **every hour** — no human needed.

---

## ✨ What It Does

Every hour, the bot:
1. 🔍 Searches Amazon (PAAPI) + Flipkart (Affiliate API) for discounted products
2. 🏷️ Filters by minimum discount %, savings amount, and price range
3. 📊 Ranks deals by discount % + absolute savings (best deals first)
4. 📤 Posts top 5 deals to your Telegram channel with image, prices, and affiliate link
5. ✅ Tracks posted deals to never repeat within 7 days

---

## 📱 Sample Post Output

```
🔥🔥 HOT DEAL 🛒 Amazon

🏷️ boAt Rockerz 450 Bluetooth Headphone (Navy Blue)

💰 Sale Price: ₹999
🏪 MRP: ₹3,490
📉 71% OFF
💵 You Save: ₹2,491

⚡ 👉 BUY NOW on Amazon

━━━━━━━━━━━━━━━━━
🔔 #Deals #Sale #Discount #AmazonIndia
📢 Join → BestDealsIndia for hourly deals!
```

---

## 🚀 Setup Guide

### Step 1 — Create Telegram Bot

1. Message `@BotFather` on Telegram
2. Send `/newbot` → name your bot → get your **Bot Token**
3. Add the bot to your channel as an **Admin** (Post Messages permission)
4. Get your channel ID: message `@userinfobot` or use `@your_channel_name`

### Step 2 — Amazon Affiliate Setup

1. Join: https://affiliate-program.amazon.in (Amazon Associates)
2. After **3 qualifying sales**, request PAAPI access from your dashboard
3. Go to **Tools → Product Advertising API** → generate Access Key + Secret Key
4. Your **Partner Tag** is your Associates ID (e.g. `yourtag-21`)

> 💡 **While waiting for PAAPI access**: set `ENABLE_AMAZON=true` with no credentials — the bot will use demo data so you can test immediately.

### Step 3 — Flipkart Affiliate Setup

1. Join: https://affiliate.flipkart.com
2. Dashboard → **API** → generate your **Affiliate ID** and **Token**

### Step 4 — Configure

```bash
git clone <this-repo>
cd discount-bot-affiliate
cp .env.example .env
nano .env   # fill in your tokens
```

### Step 5 — Run

**Docker (recommended — runs 24/7, auto-restarts):**
```bash
docker-compose up -d
docker-compose logs -f   # watch live
```

**Plain Python:**
```bash
pip install -r requirements.txt
python bot.py
```

---

## ⚙️ Key Configuration Options (`.env`)

| Variable | Default | Description |
|---|---|---|
| `POST_INTERVAL_HOURS` | `1` | How often to check & post |
| `MAX_POSTS_PER_CYCLE` | `5` | Max posts per hour |
| `MIN_DISCOUNT_PERCENT` | `20` | Minimum % discount |
| `MIN_SAVINGS_AMOUNT` | `100` | Minimum ₹ saved |
| `AMAZON_CATEGORIES` | Electronics, etc. | PAAPI search categories |
| `FLIPKART_CATEGORIES` | mobiles, etc. | Flipkart category slugs |
| `BLOCK_KEYWORDS` | — | Words to skip (e.g. `cheap,refurbished`) |
| `POSTED_TTL_DAYS` | `7` | Days before reposting same deal |
| `POST_HASHTAGS` | `#Deals #Sale` | Appended to every post |

---

## 📁 Project Structure

```
discount-bot-affiliate/
├── bot.py                    ← Run this
├── src/
│   ├── scheduler.py          ← Hourly timer loop
│   ├── amazon_fetcher.py     ← Amazon PAAPI 5.0 integration
│   ├── flipkart_fetcher.py   ← Flipkart Affiliate API integration
│   ├── deal_filter.py        ← Filter by discount/price/keywords
│   ├── telegram_poster.py    ← Format & post to Telegram
│   └── posted_tracker.py     ← Duplicate prevention (data/posted.json)
├── data/posted.json          ← Auto-created: tracks posted deals
├── logs/bot.log              ← Auto-created: activity log
├── .env.example              ← Config template
├── Dockerfile
└── docker-compose.yml
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| Bot not posting | Check `logs/bot.log`; verify bot is channel admin |
| Amazon 401 error | Check PAAPI credentials in `.env` |
| Flipkart 403 error | Verify affiliate ID + token |
| No deals found | Lower `MIN_DISCOUNT_PERCENT` or add more categories |
| Same deals reposting | Increase `POSTED_TTL_DAYS` |
| Posts look broken | Check `TELEGRAM_CHANNEL_ID` format — use `@channel` or numeric ID |

---

## 💰 How Affiliate Earnings Work

Every product link has your affiliate tag embedded. When a user clicks and buys:
- **Amazon**: 0.2% – 9% commission depending on category
- **Flipkart**: 1% – 10% commission depending on category

More subscribers + better deals = more clicks = more earnings. 🎯

---

## 📌 Deployment Tips

- **Free hosting**: Oracle Cloud Free Tier (always-free VM), Railway.app, Render.com
- **VPS**: Hetzner CX11 (~€3.29/mo), DigitalOcean Droplet
- **Monitor**: `docker-compose logs -f` or tail `logs/bot.log`
- **Reset tracker**: Delete `data/posted.json` to re-enable all past deals
