# Retail Analytics: Metrics & Data Schema

By utilizing Gemini 1.5 Pro for multimodal video understanding, we can move far beyond simple "foot traffic" and extract rich, nuanced behavioral data. When a motion/zone event triggers a video recording (e.g., a 10-second clip), we will pass that clip to Gemini with a prompt to return a structured JSON object containing the following metrics:

## 1. Core Engagement Metrics
These are the foundational metrics that mimic e-commerce tracking (like click-through rates and hover times).

*   **`zone_dwell_time_seconds` (Integer):** Total time the customer spent within the camera's defined zone.
*   **`interaction_type` (Enum):** The highest level of engagement observed.
    *   `passed_by`: Walked through the zone without stopping.
    *   `browsed`: Stopped and looked at the shelf, but no physical contact.
    *   `examined`: Picked up an item to look at it (read label, check price).
    *   `compared`: Picked up multiple items or looked back and forth between items.
*   **`conversion_outcome` (Enum):** The result of the interaction.
    *   `taken`: The customer kept the item (intent to purchase).
    *   `returned`: The customer placed the item back on the shelf (abandonment).
    *   `none`: No items were physically moved.

## 2. Product & Context Metrics
These metrics provide context on *what* was interacted with and *who* is shopping.

*   **`product_category_engaged` (String):** What section of the shelf they interacted with (e.g., "Top shelf left", or if resolution permits, "Red cereal box").
*   **`shopper_group_size` (Integer):** Was it a single shopper, a couple, or a family? (e.g., `1`, `2`, `3+`).
*   **`estimated_demographic` (String):** High-level categorization (e.g., `young_adult`, `adult`, `senior`). *Note: Keeping this generic avoids strict PII issues while still providing demographic trends.*

## 3. Example Gemini JSON Output

This is the exact JSON structure we will instruct Gemini 1.5 Pro to return for every video clip. This data will be instantly saved to Firestore.

```json
{
  "event_id": "vid_987654321",
  "timestamp": "2026-09-26T14:30:00Z",
  "zone_id": "endcap_promo_A",
  "zone_dwell_time_seconds": 12,
  "interaction_type": "compared",
  "conversion_outcome": "returned",
  "product_category_engaged": "middle_shelf_blue_bottles",
  "shopper_group_size": 1,
  "estimated_demographic": "adult",
  "behavioral_summary": "Customer stopped, picked up a blue bottle, compared it with a green bottle next to it, and ultimately returned both to the shelf."
}
```

## Why this wins hackathons:
Instead of just showing a graph of "15 people walked by," your dashboard can now query: 
> *"Show me the abandonment rate (`returned`) for adults who `examined` the middle shelf today."* 
This is exactly the kind of deep, actionable insight that retail executives are desperate for, perfectly aligning with the "Intelligent Customer and Business Experiences" theme.
