# 🚀 Instagram Daily Post Automation (n8n Workflow)

## 📌 Overview

This project automates **end-to-end Instagram posting** using **n8n**, Google Sheets, Screenshot API, Cloudinary, and Meta Graph API.

---

# 🧩 Features

* 📄 Read content from Google Sheets
* 🎨 Convert content into styled HTML slides
* 🖼 Convert HTML → Images (1080x1080)
* ☁️ Upload images to Cloudinary
* 📸 Post as Instagram Carousel
* ✍️ Auto-generate captions
* 🔗 Fetch post permalink
* ✅ Update status in Google Sheets

---

# 🏗️ Architecture Flow

```
Google Sheets → HTML → Screenshot API → Cloudinary → Instagram → Sheet Update
```

---

# 📊 Google Sheet Structure

| Column   | Description                       |
| -------- | --------------------------------- |
| id       | Unique identifier                 |
| title    | Post title                        |
| problem  | Problem statement                 |
| solution | Solution explanation              |
| code     | Code snippet                      |
| question | Quiz question                     |
| options  | Multiple options (line-separated) |
| answer   | Correct answer                    |
| caption  | Base caption                      |
| status   | pending / published               |

---

# ⚙️ Setup Guide (STEP-BY-STEP)

---

# 🖼️ 1. Screenshot API (HTML → Image)

## 🔗 Create Account

Go to:

[ScreenshotOne Dashboard](https://screenshotone.com?utm_source=chatgpt.com)

1. Sign up (free plan available)
2. Go to Dashboard
3. Copy your **Access Key**

---

## 🔑 API Details

### Endpoint:

```
https://api.screenshotone.com/take
```

---

## ⚙️ n8n Configuration

### Node: HTTP Request

**Method:** POST

### Query Parameters:

| Key        | Value           |
| ---------- | --------------- |
| access_key | YOUR_ACCESS_KEY |

---

### Body Parameters:

| Key            | Value          |
| -------------- | -------------- |
| html           | {{$json.html}} |
| viewport_width | 1080           |
| format         | png            |
| delay          | 30             |

---

## 💡 Important Notes

* `html` → Full HTML string from previous node
* `delay` → ensures CSS loads before screenshot
* Output → Binary image

---

# ☁️ 2. Cloudinary Setup (Image Hosting)

## 🔗 Create Account

Go to:

[Cloudinary Console](https://cloudinary.com?utm_source=chatgpt.com)

1. Sign up
2. Open Dashboard

---

## 🔑 Required Details

From dashboard, note:

* **Cloud Name**
* **API Key**
* **API Secret**

---

## ⚙️ Create Upload Preset

1. Go to **Settings → Upload**
2. Scroll to **Upload Presets**
3. Click **Add Upload Preset**

### Configure:

| Setting      | Value                      |
| ------------ | -------------------------- |
| Signing Mode | Unsigned                   |
| Folder       | (optional) instagram-posts |

👉 Save preset

---

## ⚙️ n8n Configuration

### Node: HTTP Request

**Method:** POST

### URL:

```
https://api.cloudinary.com/v1_1/<cloud_name>/image/upload
```

---

### Body (multipart/form-data):

| Field         | Value                       |
| ------------- | --------------------------- |
| file          | Binary (from previous node) |
| upload_preset | YOUR_PRESET_NAME            |

---

## 📦 Output

```json
{
  "url": "https://res.cloudinary.com/..."
}
```

👉 This URL is used for Instagram upload

---

# 📸 3. Instagram Graph API Setup

## 🔗 Meta Developer Portal

[Meta Developers](https://developers.facebook.com?utm_source=chatgpt.com)

---

## Required:

* Instagram Business Account
* Facebook Page linked to Instagram
* App with permissions:

  * instagram_basic
  * instagram_content_publish

---

## 🔑 Get Access Token

Use Graph API Explorer:

```
pages_show_list
instagram_basic
instagram_content_publish
```

---

## 📌 Get Instagram User ID

```
GET /me/accounts
```

Then:

```
GET /{page-id}?fields=instagram_business_account
```

---

# 🚀 Instagram Posting Flow

---

## 1. Upload Images

```
POST /{ig-user-id}/media
```

Params:

* image_url
* is_carousel_item=true

---

## 2. Create Carousel

```
POST /media
```

Params:

* media_type=CAROUSEL
* children=comma_separated_ids
* caption

---

## 3. Publish

```
POST /media_publish
```

---

## 4. Get Permalink

```
GET /{media-id}?fields=permalink
```

---

# 🚀 How to Run

1. Import workflow into n8n

2. Configure:

   * Google Sheets OAuth
   * Screenshot API key
   * Cloudinary preset
   * Meta Graph API token

3. Add row in sheet:

```
status = pending
```

4. Execute workflow

---

# 🎯 Output

* Instagram Carousel Post
* Caption with engagement
* Sheet updated with:

  * status = published
  * permalink

---

# 💡 Best Practices

* Keep images 1080x1080
* Avoid long captions (>2200 chars)
* Use strong hooks in first line
* Ensure Cloudinary URLs are public

---

# ⚠️ Common Issues

| Issue             | Fix              |
| ----------------- | ---------------- |
| Image not posting | Check public URL |
| Carousel fails    | Ensure 2+ images |
| API error         | Refresh token    |
| Blank image       | Increase delay   |

---

# 🔮 Future Enhancements

* ⏱ Cron scheduling
* 🤖 AI caption generator
* 📊 Analytics tracking
* 📲 Story posting with link

---

# 🧠 Summary

This workflow creates a **fully automated Instagram content engine**:

✔ Content → Visual → Publish
✔ No manual effort
✔ Scalable system

---

Happy Automating 🚀
