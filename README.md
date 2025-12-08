Recipe-Data-Pipeline
A robust end-to-end data pipeline that fetches recipe data from the Spoonacular API, transforms it into a clean format, stores it in PostgreSQL, and provides comprehensive monitoring and reliability features.

🎯 Project Overview
This pipeline demonstrates best practices in data engineering, including:

Data Extraction: Resilient API client with retry logic and error handling
Data Transformation: Clean, normalized data with calculated fields
Data Storage: PostgreSQL with optimized schema and upsert logic
Monitoring & Reliability: Comprehensive logging, health tracking, and alerting
Dashboard: Retool integration for data visualization and pipeline monitoring

🚀 Features

Data Pipeline
✅ Robust API Integration: Spoonacular API with automatic retries and rate limiting

✅ Data Transformation:
Normalize nested JSON to relational format
Calculate health score categories
Clean HTML from text fields
Add derived metrics (price categories, cook time ranges)

✅ Reliable Storage:
Upsert logic prevents duplicates
Transaction management ensures data integrity
Optimized indexes for query performance

Monitoring & Reliability
✅ Multi-level Logging: Console (colored), file, and database logging
✅ Pipeline Status Tracking: Success/failure rates, execution time, record counts
✅ Health Checks: Last successful run, error rates, performance metrics
✅ Alerting: Optional Slack and email notifications for failures
✅ Error Handling: Graceful degradation, detailed error logging, retry mechanisms

Dashboard & Visualization
✅ Retool Integration: Pre-built queries and dashboard layout
✅ Key Metrics: Recipe counts, health scores, price distribution, diet types
✅ Data Exploration: Searchable recipe table, ingredient analysis, nutrition stats
✅ Pipeline Monitoring: Execution history, error logs, health status

🛠️ Technology Stack
Language: Python 3.11+
API: Spoonacular Recipe API
Database: PostgreSQL 14+
Dashboard: Retool
Key Libraries:
requests: API calls
psycopg2: PostgreSQL driver
tenacity: Retry logic
colorlog: Colored logging
python-dotenv: Environment management

📋 Prerequisites
Python 3.11 or higher
PostgreSQL 14 or higher
Spoonacular API key (free tier available at https://spoonacular.com/food-api)
Retool account (free tier available at https://retool.com)

Edit .env with your credentials:

# Required
SPOONACULAR_API_KEY=your_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=recipe_pipeline
DB_USER=postgres
DB_PASSWORD=your_password

# Optional (for alerting)
SLACK_WEBHOOK_URL=your_slack_webhook
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=recipient@email.com

Run Pipeline Command : python -m src.pipeline
Pipeline Health Check: python -m src.pipeline --health-check 

🗄️ Database Schema
Tables
recipes: Main recipe information

Basic details (title, servings, cook time, price)
Health metrics (health score, categories)
Diet flags (vegetarian, vegan, gluten-free, etc.)
Text content (summary, instructions)
recipe_ingredients: Ingredient details

Ingredient name, amount, unit
Foreign key to recipes
recipe_nutrition: Nutritional information

Calories, macronutrients, fiber, sugar, sodium
One-to-one relationship with recipes
pipeline_logs: Detailed execution logs

Timestamp, level, module, message
Error details and execution time
pipeline_status: Pipeline run tracking

Run ID, status, timestamps
Records processed/failed, duration

Views
recipe_summary: Denormalized recipe data for dashboards
pipeline_health: Aggregated pipeline metrics
