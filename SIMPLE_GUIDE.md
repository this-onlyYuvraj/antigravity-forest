# The Simple Guide: How Our Deforestation Detector Works 🌳🔍

Think of this entire software system as a **24/7 automated security guard** for the Amazon Rainforest. Its job is to watch the forest day and night, even when it's raining or cloudy, and instantly tell us if someone cuts down trees.

Here is the detailed breakdown of how it works, explained simply.

---

## 1. The "Eyes in the Sky" (Satellites) 🛰️
Normally, satellites are just like phone cameras—they need sunlight and clear skies to take a picture. If there are clouds (which happens a lot in the rainforest!), they can't see anything.

**Our Solution: Radar Vision**
We use a special satellite called **Sentinel-1**. Instead of taking a photo with light, it shoots **Radar beams** down at the earth.
-   **Think of it like a bat** using echolocation. It sends a signal down and listens for the echo.
-   **Trees are rough and messy**, so they bounce the signal back strongly.
-   **Bare ground is flat**, so the signal bounces away (like a mirror).
-   **Superpower**: Radar goes right through clouds, rain, and smoke. We can "see" the forest 365 days a year.

---

## 2. The "Brain" (The Python Robot) 🤖
Every day, our computer program (the Python pipeline) wakes up and checks if the satellite has sent new data.

**Step A: Spot the Difference**
The program plays a giant game of "Spot the Difference."
-   It keeps a memory of what the forest looked like yesterday, last week, and last month (the **Baseline**).
-   It looks at the new image. If a patch of forest used to be "loud" (bouncing radar back) and suddenly goes "quiet" (flat ground), the computer gets suspicious.
-   This is our **Adaptive Threshold Algorithm**: It knows that wind moving the trees is normal, but a sudden massive drop in signal is definitely NOT normal.

**Step B: The Second Opinion (AI Check)**
Sometimes, heavy rain can look a bit like deforestation. We don't want to send false alarms.
-   So, we ask a second, smarter brain (a **Neural Network AI**).
-   We show it the "history" of that specific spot.
-   The AI looks at the pattern and decides: *"No, that's just a storm"* OR *"Yes, that looks exactly like a chainsaw pattern."*

---

## 3. The "Filing Cabinet" (The Database) 🗄️
Once the Brain finds a confirmed spot of deforestation, it needs to save it.
-   It writes a report card for that alert: **Where** is it? **How big** is it? **When** did it happen?
-   It also checks a map of **Protected Areas** (Indigenous lands or National Parks).
-   If the cut trees are inside a Protected Area, it stamps the report **"URGENT" (Tier 2)**. If it's on regular land, it stamps it **"Standard" (Tier 1)**.

---

## 4. The "Control Room" (The Dashboard) 🖥️
This is what the ranger or user sees on their screen (the Website).
-   The website asks the Filing Cabinet: *"Do you have any new alerts?"*
-   If yes, it draws them on the map.
-   **Red Boxes**: High-risk alerts (someone is cutting trees in a protected area!).
-   **Orange Boxes**: Standard alerts.
-   **Amber Dotted Line**: This shows the boundaries of the town we are watching (Novo Progresso), so you know exactly where the action is happening.

### Why is this better than the old way?
-   **Old Way**: Wait for a cloud-free day (could take weeks), take a photo, have a human look at it. By then, the forest is gone.
-   **Our Way**: Radar sees through clouds. The computer checks millions of spots in seconds. We know about the deforestation **while it is happening**, not weeks later.

---

## 5. Where does it live? (The Folders)

If you look at the files on the computer, here is where each "Character" lives:

| Character | Folder Name | What it contains |
| :--- | :--- | :--- |
| **The Brain** 🤖 | `backend-python` | The Python scripts that do the math and "Spot the Difference". |
| **The Messenger** 📨 | `backend-api` | The web server that passes messages between the Brain and the Dashboard. |
| **The Control Room** 🖥️ | `frontend` | The Website you see (colors, map, buttons). |
| **The Filing Cabinet** 🗄️ | `database` | The SQL files that set up the storage system. |
