"""
Setup verification script.
Tests configuration, database connection, and API access.
"""

import sys
from src.config import Config

def test_configuration():
    """Test configuration loading."""
    print("\n" + "="*60)
    print("Testing Configuration")
    print("="*60)
    
    try:
        Config.validate()
        print("✓ Configuration validated successfully")
        print(f"  - API Key: {'*' * 20}{Config.SPOONACULAR_API_KEY[-4:]}")
        print(f"  - Database: {Config.DB_NAME}")
        print(f"  - Host: {Config.DB_HOST}:{Config.DB_PORT}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_database_connection():
    """Test database connectivity."""
    print("\n" + "="*60)
    print("Testing Database Connection")
    print("="*60)
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            connect_timeout=10
        )
        
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✓ Connected to PostgreSQL")
            print(f"  - Version: {version.split(',')[0]}")
            
            # Check if tables exist
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            
            if tables:
                print(f"✓ Found {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table}")
            else:
                print("⚠ No tables found. Run schema.sql to create tables.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("\nTroubleshooting steps:")
        print("1. Ensure PostgreSQL is running")
        print("2. Verify database credentials in .env")
        print("3. Check if database exists: psql -l")
        print("4. Run schema: psql -U postgres -d recipe_pipeline -f schema.sql")
        return False

def test_api_access():
    """Test Spoonacular API access."""
    print("\n" + "="*60)
    print("Testing Spoonacular API Access")
    print("="*60)
    
    try:
        import requests
        
        url = f"{Config.SPOONACULAR_BASE_URL}/recipes/random"
        params = {
            'apiKey': Config.SPOONACULAR_API_KEY,
            'number': 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        recipes = data.get('recipes', [])
        
        if recipes:
            recipe = recipes[0]
            print("✓ API access successful")
            print(f"  - Test recipe: {recipe.get('title')}")
            print(f"  - Recipe ID: {recipe.get('id')}")
            
            # Check rate limit headers
            if 'X-API-Quota-Used' in response.headers:
                used = response.headers['X-API-Quota-Used']
                limit = response.headers.get('X-API-Quota-Limit', 'unknown')
                print(f"  - API Quota: {used}/{limit}")
        else:
            print("⚠ API returned no recipes")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("✗ Invalid API key")
            print("  Get your key at: https://spoonacular.com/food-api")
        elif e.response.status_code == 402:
            print("✗ API quota exceeded")
            print("  Check your plan at: https://spoonacular.com/food-api/console")
        else:
            print(f"✗ API error: {e}")
        return False
        
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Recipe Data Pipeline - Setup Verification")
    print("="*60)
    
    results = {
        'Configuration': test_configuration(),
        'Database': test_database_connection(),
        'API': test_api_access()
    }
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed! You're ready to run the pipeline.")
        print("\nNext steps:")
        print("  1. Run pipeline: python src/pipeline.py")
        print("  2. Check results: python src/pipeline.py --health-check")
        print("  3. Set up dashboard: See docs/RETOOL_SETUP.md")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()