-- Spoonacular Data Pipeline Database Schema
-- PostgreSQL

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS recipe_ingredients CASCADE;
DROP TABLE IF EXISTS recipe_nutrition CASCADE;
DROP TABLE IF EXISTS recipes CASCADE;
DROP TABLE IF EXISTS pipeline_logs CASCADE;
DROP TABLE IF EXISTS pipeline_status CASCADE;

-- Main recipes table
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    image_url TEXT,
    servings INTEGER,
    ready_in_minutes INTEGER,
    price_per_serving DECIMAL(10, 2),
    health_score INTEGER,
    health_category VARCHAR(50),
    vegetarian BOOLEAN DEFAULT FALSE,
    vegan BOOLEAN DEFAULT FALSE,
    gluten_free BOOLEAN DEFAULT FALSE,
    dairy_free BOOLEAN DEFAULT FALSE,
    very_healthy BOOLEAN DEFAULT FALSE,
    cheap BOOLEAN DEFAULT FALSE,
    very_popular BOOLEAN DEFAULT FALSE,
    sustainable BOOLEAN DEFAULT FALSE,
    summary TEXT,
    instructions TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recipe ingredients table
CREATE TABLE recipe_ingredients (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_name VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2),
    unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recipe nutrition table
CREATE TABLE recipe_nutrition (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE CASCADE,
    calories DECIMAL(10, 2),
    protein DECIMAL(10, 2),
    fat DECIMAL(10, 2),
    carbohydrates DECIMAL(10, 2),
    fiber DECIMAL(10, 2),
    sugar DECIMAL(10, 2),
    sodium DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(recipe_id)
);

-- Pipeline execution logs
CREATE TABLE pipeline_logs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(20) NOT NULL,
    module VARCHAR(100),
    message TEXT NOT NULL,
    error_details TEXT,
    execution_time_ms INTEGER
);

-- Pipeline status tracking
CREATE TABLE pipeline_status (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(36) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'running', 'success', 'failed'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    duration_seconds INTEGER
);

-- Create indexes for better query performance
CREATE INDEX idx_recipes_health_score ON recipes(health_score);
CREATE INDEX idx_recipes_price ON recipes(price_per_serving);
CREATE INDEX idx_recipes_ready_time ON recipes(ready_in_minutes);
CREATE INDEX idx_recipes_vegetarian ON recipes(vegetarian);
CREATE INDEX idx_recipes_vegan ON recipes(vegan);
CREATE INDEX idx_recipe_ingredients_recipe_id ON recipe_ingredients(recipe_id);
CREATE INDEX idx_recipe_nutrition_recipe_id ON recipe_nutrition(recipe_id);
CREATE INDEX idx_pipeline_logs_run_id ON pipeline_logs(run_id);
CREATE INDEX idx_pipeline_logs_timestamp ON pipeline_logs(timestamp);
CREATE INDEX idx_pipeline_status_status ON pipeline_status(status);
CREATE INDEX idx_pipeline_status_started_at ON pipeline_status(started_at);

-- Create view for dashboard queries
CREATE OR REPLACE VIEW recipe_summary AS
SELECT 
    r.id,
    r.title,
    r.servings,
    r.ready_in_minutes,
    r.price_per_serving,
    r.health_score,
    r.health_category,
    r.vegetarian,
    r.vegan,
    r.gluten_free,
    n.calories,
    n.protein,
    n.carbohydrates,
    COUNT(ri.id) as ingredient_count
FROM recipes r
LEFT JOIN recipe_nutrition n ON r.id = n.recipe_id
LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
GROUP BY r.id, r.title, r.servings, r.ready_in_minutes, r.price_per_serving, 
         r.health_score, r.health_category, r.vegetarian, r.vegan, r.gluten_free,
         n.calories, n.protein, n.carbohydrates;

-- Create view for monitoring dashboard
CREATE OR REPLACE VIEW pipeline_health AS
SELECT 
    ps.run_id,
    ps.status,
    ps.started_at,
    ps.completed_at,
    ps.records_processed,
    ps.records_failed,
    ps.duration_seconds,
    COUNT(pl.id) FILTER (WHERE pl.level = 'ERROR') as error_count,
    COUNT(pl.id) FILTER (WHERE pl.level = 'WARNING') as warning_count
FROM pipeline_status ps
LEFT JOIN pipeline_logs pl ON ps.run_id = pl.run_id
GROUP BY ps.run_id, ps.status, ps.started_at, ps.completed_at, 
         ps.records_processed, ps.records_failed, ps.duration_seconds
ORDER BY ps.started_at DESC;

COMMENT ON TABLE recipes IS 'Stores recipe information from Spoonacular API';
COMMENT ON TABLE recipe_ingredients IS 'Stores ingredients for each recipe';
COMMENT ON TABLE recipe_nutrition IS 'Stores nutritional information for each recipe';
COMMENT ON TABLE pipeline_logs IS 'Stores detailed pipeline execution logs';
COMMENT ON TABLE pipeline_status IS 'Tracks pipeline run status and metrics';