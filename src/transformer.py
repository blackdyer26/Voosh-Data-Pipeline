"""
Data transformation module for cleaning and normalizing recipe data.
Transforms nested JSON into relational database format.
"""

from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal
import re
from src.monitor import PipelineMonitor

class RecipeTransformer:
    """Transforms raw API data into clean, normalized format."""
    
    def __init__(self, monitor: PipelineMonitor):
        """
        Initialize the transformer.
        
        Args:
            monitor: PipelineMonitor instance for logging
        """
        self.monitor = monitor
    
    def transform_recipe(self, raw_recipe: Dict[str, Any]) -> Tuple[Dict, List[Dict], Optional[Dict]]:
        """
        Transform raw recipe data into normalized format.
        
        Args:
            raw_recipe: Raw recipe data from API
            
        Returns:
            Tuple of (recipe_dict, ingredients_list, nutrition_dict)
        """
        try:
            # Transform main recipe data
            recipe = self._transform_recipe_main(raw_recipe)
            
            # Transform ingredients
            ingredients = self._transform_ingredients(raw_recipe)
            
            # Transform nutrition
            nutrition = self._transform_nutrition(raw_recipe)
            
            self.monitor.log("DEBUG", f"Transformed recipe: {recipe['title']}", "transformer")
            
            return recipe, ingredients, nutrition
            
        except Exception as e:
            self.monitor.log("ERROR", f"Failed to transform recipe: {e}", "transformer", str(e))
            raise
    
    def _transform_recipe_main(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Transform main recipe fields."""
        
        # Calculate health category based on health score
        health_score = raw.get('healthScore', 0)
        health_category = self._categorize_health_score(health_score)
        
        # Clean summary text
        summary = self._clean_html(raw.get('summary', ''))
        
        # Clean instructions
        instructions = self._clean_html(raw.get('instructions', ''))
        
        recipe = {
            'id': raw['id'],
            'title': raw['title'][:500],  # Limit length
            'image_url': raw.get('image'),
            'servings': raw.get('servings'),
            'ready_in_minutes': raw.get('readyInMinutes'),
            'price_per_serving': self._safe_decimal(raw.get('pricePerServing')),
            'health_score': health_score,
            'health_category': health_category,
            'vegetarian': raw.get('vegetarian', False),
            'vegan': raw.get('vegan', False),
            'gluten_free': raw.get('glutenFree', False),
            'dairy_free': raw.get('dairyFree', False),
            'very_healthy': raw.get('veryHealthy', False),
            'cheap': raw.get('cheap', False),
            'very_popular': raw.get('veryPopular', False),
            'sustainable': raw.get('sustainable', False),
            'summary': summary,
            'instructions': instructions,
            'source_url': raw.get('sourceUrl')
        }
        
        return recipe
    
    def _transform_ingredients(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform ingredients list."""
        ingredients = []
        
        extended_ingredients = raw.get('extendedIngredients', [])
        
        for ing in extended_ingredients:
            ingredient = {
                'recipe_id': raw['id'],
                'ingredient_name': ing.get('name', ing.get('original', 'Unknown'))[:255],
                'amount': self._safe_decimal(ing.get('amount')),
                'unit': ing.get('unit', '')[:50]
            }
            ingredients.append(ingredient)
        
        return ingredients
    
    def _transform_nutrition(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform nutrition information."""
        nutrition_data = raw.get('nutrition', {})
        
        if not nutrition_data:
            return None
        
        nutrients = nutrition_data.get('nutrients', [])
        
        # Create a lookup dictionary
        nutrient_map = {n['name']: n['amount'] for n in nutrients}
        
        nutrition = {
            'recipe_id': raw['id'],
            'calories': self._safe_decimal(nutrient_map.get('Calories')),
            'protein': self._safe_decimal(nutrient_map.get('Protein')),
            'fat': self._safe_decimal(nutrient_map.get('Fat')),
            'carbohydrates': self._safe_decimal(nutrient_map.get('Carbohydrates')),
            'fiber': self._safe_decimal(nutrient_map.get('Fiber')),
            'sugar': self._safe_decimal(nutrient_map.get('Sugar')),
            'sodium': self._safe_decimal(nutrient_map.get('Sodium'))
        }
        
        return nutrition
    
    def _categorize_health_score(self, score: int) -> str:
        """Categorize health score into ranges."""
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Fair'
        elif score >= 20:
            return 'Poor'
        else:
            return 'Very Poor'
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ''
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None:
            return None
        
        try:
            return Decimal(str(value))
        except:
            return None
    
    def validate_transformed_data(self, recipe: Dict, ingredients: List[Dict], 
                                  nutrition: Optional[Dict]) -> bool:
        """
        Validate transformed data before loading.
        
        Args:
            recipe: Transformed recipe dictionary
            ingredients: List of ingredient dictionaries
            nutrition: Nutrition dictionary
            
        Returns:
            True if valid, False otherwise
        """
        # Check required recipe fields
        if not recipe.get('id') or not recipe.get('title'):
            self.monitor.log("WARNING", "Recipe missing required fields", "transformer")
            return False
        
        # Check ingredients
        if not ingredients:
            self.monitor.log("WARNING", f"Recipe {recipe['id']} has no ingredients", "transformer")
        
        # Nutrition is optional
        
        return True
    
    def transform_batch(self, raw_recipes: List[Dict[str, Any]]) -> List[Tuple[Dict, List[Dict], Optional[Dict]]]:
        """
        Transform a batch of recipes.
        
        Args:
            raw_recipes: List of raw recipe dictionaries
            
        Returns:
            List of transformed recipe tuples
        """
        self.monitor.log("INFO", f"Transforming {len(raw_recipes)} recipes", "transformer")
        
        transformed = []
        failed = 0
        
        for raw_recipe in raw_recipes:
            try:
                recipe_data = self.transform_recipe(raw_recipe)
                
                # Validate
                if self.validate_transformed_data(*recipe_data):
                    transformed.append(recipe_data)
                else:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                recipe_id = raw_recipe.get('id', 'unknown')
                self.monitor.log("ERROR", f"Failed to transform recipe {recipe_id}: {e}", 
                               "transformer", str(e))
        
        self.monitor.log("INFO", f"Successfully transformed {len(transformed)} recipes, {failed} failed", 
                        "transformer")
        
        return transformed