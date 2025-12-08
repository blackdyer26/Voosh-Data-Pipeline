"""
Data extraction module for fetching recipe data from Spoonacular API.
Implements robust error handling, retries, and rate limiting.
"""

import time
from typing import List, Dict, Any, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import Config
from src.monitor import PipelineMonitor

class SpoonacularExtractor:
    """Extracts recipe data from Spoonacular API with resilience features."""
    
    def __init__(self, monitor: PipelineMonitor):
        """
        Initialize the extractor.
        
        Args:
            monitor: PipelineMonitor instance for logging
        """
        self.monitor = monitor
        self.base_url = Config.SPOONACULAR_BASE_URL
        self.api_key = Config.SPOONACULAR_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RecipeDataPipeline/1.0'
        })
    
    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=Config.RETRY_DELAY, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout))
    )
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make API request with retry logic.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            requests.exceptions.RequestException: If request fails after retries
        """
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        start_time = time.time()
        
        try:
            self.monitor.log("DEBUG", f"Making request to {endpoint}", "extractor")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            execution_time = int((time.time() - start_time) * 1000)
            self.monitor.log("DEBUG", f"Request successful: {endpoint}", "extractor", 
                           execution_time_ms=execution_time)
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 402:
                error_msg = "API quota exceeded. Please check your Spoonacular plan."
                self.monitor.log("ERROR", error_msg, "extractor", str(e))
                raise Exception(error_msg)
            elif e.response.status_code == 401:
                error_msg = "Invalid API key. Please check your SPOONACULAR_API_KEY."
                self.monitor.log("ERROR", error_msg, "extractor", str(e))
                raise Exception(error_msg)
            else:
                self.monitor.log("ERROR", f"HTTP error: {e}", "extractor", str(e))
                raise
                
        except requests.exceptions.Timeout as e:
            self.monitor.log("WARNING", f"Request timeout: {endpoint}", "extractor", str(e))
            raise
            
        except requests.exceptions.RequestException as e:
            self.monitor.log("ERROR", f"Request failed: {endpoint}", "extractor", str(e))
            raise
    
    def fetch_random_recipes(self, number: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch random recipes from Spoonacular API.
        
        Args:
            number: Number of recipes to fetch
            
        Returns:
            List of recipe dictionaries
        """
        self.monitor.log("INFO", f"Fetching {number} random recipes", "extractor")
        
        try:
            response = self._make_request("recipes/random", {"number": number})
            recipes = response.get('recipes', [])
            
            self.monitor.log("INFO", f"Successfully fetched {len(recipes)} recipes", "extractor")
            return recipes
            
        except Exception as e:
            self.monitor.log("ERROR", f"Failed to fetch random recipes: {e}", "extractor", str(e))
            return []
    
    def fetch_recipe_details(self, recipe_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed information for a specific recipe.
        
        Args:
            recipe_id: Spoonacular recipe ID
            
        Returns:
            Recipe details dictionary or None if failed
        """
        try:
            endpoint = f"recipes/{recipe_id}/information"
            params = {"includeNutrition": "true"}
            
            recipe_data = self._make_request(endpoint, params)
            
            self.monitor.log("DEBUG", f"Fetched details for recipe {recipe_id}", "extractor")
            return recipe_data
            
        except Exception as e:
            self.monitor.log("WARNING", f"Failed to fetch recipe {recipe_id}: {e}", 
                           "extractor", str(e))
            return None
    
    def fetch_batch_recipes(self, batch_size: int = None) -> List[Dict[str, Any]]:
        """
        Fetch a batch of recipes with full details.
        
        Args:
            batch_size: Number of recipes to fetch (uses Config.BATCH_SIZE if None)
            
        Returns:
            List of complete recipe dictionaries
        """
        if batch_size is None:
            batch_size = Config.BATCH_SIZE
        
        self.monitor.log("INFO", f"Starting batch extraction of {batch_size} recipes", "extractor")
        
        # Fetch random recipes
        recipes = self.fetch_random_recipes(batch_size)
        
        if not recipes:
            self.monitor.log("WARNING", "No recipes fetched from API", "extractor")
            return []
        
        # Enrich with detailed information
        detailed_recipes = []
        for recipe in recipes:
            recipe_id = recipe.get('id')
            if not recipe_id:
                continue
            
            # Add small delay to respect rate limits
            time.sleep(0.5)
            
            detailed_recipe = self.fetch_recipe_details(recipe_id)
            if detailed_recipe:
                detailed_recipes.append(detailed_recipe)
        
        self.monitor.log("INFO", f"Successfully extracted {len(detailed_recipes)} complete recipes", 
                        "extractor")
        
        return detailed_recipes
    
    def validate_recipe_data(self, recipe: Dict[str, Any]) -> bool:
        """
        Validate that recipe has required fields.
        
        Args:
            recipe: Recipe dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['id', 'title']
        
        for field in required_fields:
            if field not in recipe or recipe[field] is None:
                self.monitor.log("WARNING", f"Recipe missing required field: {field}", "extractor")
                return False
        
        return True