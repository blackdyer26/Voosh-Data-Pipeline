"""
Data loading module for storing transformed data in PostgreSQL.
Implements upsert logic to prevent duplicates.
"""

from typing import List, Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_values
from psycopg2 import sql
from src.monitor import PipelineMonitor

class PostgreSQLLoader:
    """Loads transformed data into PostgreSQL database."""
    
    def __init__(self, db_connection, monitor: PipelineMonitor):
        """
        Initialize the loader.
        
        Args:
            db_connection: psycopg2 database connection
            monitor: PipelineMonitor instance for logging
        """
        self.db_conn = db_connection
        self.monitor = monitor
    
    def load_recipe(self, recipe: Dict[str, Any], ingredients: List[Dict[str, Any]], 
                   nutrition: Optional[Dict[str, Any]]) -> bool:
        """
        Load a single recipe with its ingredients and nutrition.
        
        Args:
            recipe: Recipe dictionary
            ingredients: List of ingredient dictionaries
            nutrition: Nutrition dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_conn.cursor() as cur:
                # Start transaction
                cur.execute("BEGIN")
                
                # Upsert recipe (update if exists, insert if not)
                self._upsert_recipe(cur, recipe)
                
                # Delete existing ingredients for this recipe
                cur.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", (recipe['id'],))
                
                # Insert ingredients
                if ingredients:
                    self._insert_ingredients(cur, ingredients)
                
                # Upsert nutrition
                if nutrition:
                    self._upsert_nutrition(cur, nutrition)
                
                # Commit transaction
                cur.execute("COMMIT")
                
            self.monitor.log("DEBUG", f"Loaded recipe {recipe['id']}: {recipe['title']}", "loader")
            return True
            
        except Exception as e:
            self.db_conn.rollback()
            self.monitor.log("ERROR", f"Failed to load recipe {recipe.get('id')}: {e}", 
                           "loader", str(e))
            return False
    
    def _upsert_recipe(self, cursor, recipe: Dict[str, Any]):
        """Upsert recipe into recipes table."""
        query = sql.SQL("""
            INSERT INTO recipes (
                id, title, image_url, servings, ready_in_minutes, price_per_serving,
                health_score, health_category, vegetarian, vegan, gluten_free, dairy_free,
                very_healthy, cheap, very_popular, sustainable, summary, instructions, source_url
            ) VALUES (
                %(id)s, %(title)s, %(image_url)s, %(servings)s, %(ready_in_minutes)s, %(price_per_serving)s,
                %(health_score)s, %(health_category)s, %(vegetarian)s, %(vegan)s, %(gluten_free)s, %(dairy_free)s,
                %(very_healthy)s, %(cheap)s, %(very_popular)s, %(sustainable)s, %(summary)s, %(instructions)s, %(source_url)s
            )
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                image_url = EXCLUDED.image_url,
                servings = EXCLUDED.servings,
                ready_in_minutes = EXCLUDED.ready_in_minutes,
                price_per_serving = EXCLUDED.price_per_serving,
                health_score = EXCLUDED.health_score,
                health_category = EXCLUDED.health_category,
                vegetarian = EXCLUDED.vegetarian,
                vegan = EXCLUDED.vegan,
                gluten_free = EXCLUDED.gluten_free,
                dairy_free = EXCLUDED.dairy_free,
                very_healthy = EXCLUDED.very_healthy,
                cheap = EXCLUDED.cheap,
                very_popular = EXCLUDED.very_popular,
                sustainable = EXCLUDED.sustainable,
                summary = EXCLUDED.summary,
                instructions = EXCLUDED.instructions,
                source_url = EXCLUDED.source_url,
                updated_at = CURRENT_TIMESTAMP
        """)
        
        cursor.execute(query, recipe)
    
    def _insert_ingredients(self, cursor, ingredients: List[Dict[str, Any]]):
        """Insert ingredients into recipe_ingredients table."""
        if not ingredients:
            return
        
        query = """
            INSERT INTO recipe_ingredients (recipe_id, ingredient_name, amount, unit)
            VALUES %s
        """
        
        values = [
            (ing['recipe_id'], ing['ingredient_name'], ing['amount'], ing['unit'])
            for ing in ingredients
        ]
        
        execute_values(cursor, query, values)
    
    def _upsert_nutrition(self, cursor, nutrition: Dict[str, Any]):
        """Upsert nutrition into recipe_nutrition table."""
        query = sql.SQL("""
            INSERT INTO recipe_nutrition (
                recipe_id, calories, protein, fat, carbohydrates, fiber, sugar, sodium
            ) VALUES (
                %(recipe_id)s, %(calories)s, %(protein)s, %(fat)s, %(carbohydrates)s, 
                %(fiber)s, %(sugar)s, %(sodium)s
            )
            ON CONFLICT (recipe_id) DO UPDATE SET
                calories = EXCLUDED.calories,
                protein = EXCLUDED.protein,
                fat = EXCLUDED.fat,
                carbohydrates = EXCLUDED.carbohydrates,
                fiber = EXCLUDED.fiber,
                sugar = EXCLUDED.sugar,
                sodium = EXCLUDED.sodium
        """)
        
        cursor.execute(query, nutrition)
    
    def load_batch(self, transformed_recipes: List[Tuple[Dict, List[Dict], Optional[Dict]]]) -> Tuple[int, int]:
        """
        Load a batch of recipes.
        
        Args:
            transformed_recipes: List of (recipe, ingredients, nutrition) tuples
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        self.monitor.log("INFO", f"Loading {len(transformed_recipes)} recipes to database", "loader")
        
        successful = 0
        failed = 0
        
        for recipe, ingredients, nutrition in transformed_recipes:
            if self.load_recipe(recipe, ingredients, nutrition):
                successful += 1
                self.monitor.increment_processed()
            else:
                failed += 1
                self.monitor.increment_failed()
        
        self.monitor.log("INFO", f"Loaded {successful} recipes successfully, {failed} failed", "loader")
        
        return successful, failed
    
    def get_recipe_count(self) -> int:
        """Get total number of recipes in database."""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM recipes")
                count = cur.fetchone()[0]
                return count
        except Exception as e:
            self.monitor.log("ERROR", f"Failed to get recipe count: {e}", "loader")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_recipes,
                        AVG(health_score) as avg_health_score,
                        AVG(price_per_serving) as avg_price,
                        AVG(ready_in_minutes) as avg_cook_time,
                        COUNT(*) FILTER (WHERE vegetarian = true) as vegetarian_count,
                        COUNT(*) FILTER (WHERE vegan = true) as vegan_count,
                        COUNT(*) FILTER (WHERE gluten_free = true) as gluten_free_count
                    FROM recipes
                """)
                
                result = cur.fetchone()
                
                return {
                    'total_recipes': result[0],
                    'avg_health_score': float(result[1]) if result[1] else 0,
                    'avg_price_per_serving': float(result[2]) if result[2] else 0,
                    'avg_cook_time_minutes': float(result[3]) if result[3] else 0,
                    'vegetarian_count': result[4],
                    'vegan_count': result[5],
                    'gluten_free_count': result[6]
                }
        except Exception as e:
            self.monitor.log("ERROR", f"Failed to get statistics: {e}", "loader")
            return {}