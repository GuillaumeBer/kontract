
import logging
from engine.filters import rank_input_listings
from fetcher.listings import fetch_listings_mock
from basket.panier_state import get_or_create_basket
from data.database import init_db

logging.basicConfig(level=logging.INFO)
init_db()

def test_pipeline():
    print("\n--- Testing Advanced Logic Pipeline ---")
    
    # 1. Mock Opportunity/Skin data
    input_skin_name = "Mock AK-47 | Redline (Field-Tested)"
    median_price = 15.0
    
    # 2. Mock Basket
    print(f"Baskets: Fetching or creating for demo_user...")
    ps = get_or_create_basket("demo_user", "mock_skin_id", "mock_coll_id")
    initial_metrics = ps.get_current_metrics()
    print(f"  Current Basket: {ps.n_bought}/{ps.n_total} items, Cost: {initial_metrics['total_cost']:.2f}€")

    # 3. Fetch/Mock Listings
    print(f"Listings: Generating 5 mock listings around {median_price}€...")
    raw_listings = fetch_listings_mock(input_skin_name, median_price, n=5)
    for l in raw_listings:
        print(f"  - Item {l['item_id']}: {l['price']}€, Float: {l['float_value']}")

    # 4. Filter & Score
    target_data = {
        "median_price": median_price,
        "float_min": 0.0,
        "float_max": 1.0,
        "max_input_price": median_price * 1.2,
        "stattrak": False,
        "skin_float_min": 0.0,
        "skin_float_max": 1.0,
    }
    print(f"Scoring: Running rank_input_listings...")
    results = rank_input_listings(raw_listings, target_data, initial_metrics)
    
    print(f"Results: {results['passed_filters']} passed, {results['rejected']} rejected.")
    for l in results["top_listings"]:
        print(f"  ⭐ Score: {l['score']} | Price: {l['price']}€ | Float: {l['float_value']} | Recommended: {l['recommended']}")

    print("\n--- Pipeline Check OK ---")

if __name__ == "__main__":
    test_pipeline()
