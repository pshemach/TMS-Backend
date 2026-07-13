# TMS Backend API

This repository contains the backend service for the Transportation Management System (TMS). It is built with FastAPI and exposes a set of REST APIs to manage fleets, vehicles, shops, depots, orders, optimization workflows, and related constraints.

## Overview

The backend is organized around a modular API layer and SQLAlchemy models. The application initializes the FastAPI app, registers the available routers, and creates database tables automatically using the ORM metadata.

The current API includes routes for:

- Shops
- Depots
- Fleets
- Vehicles
- Vehicle constraints
- Geo constraints
- Predefined routes
- Orders
- Order groups
- Optimization
- Jobs

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- Pydantic
- Uvicorn
- CORS middleware for cross-origin access

## Project Structure

```text
TMS-Backend/
├── main.py
├── src/
│   ├── api/
│   │   └── routes/
│   │       ├── fleet_routes.py
│   │       ├── shop_routes.py
│   │       ├── depot_routes.py
│   │       ├── vehicle_routes.py
│   │       ├── vehicle_constrain_routes.py
│   │       ├── geo_constraint_routes.py
│   │       ├── predefined_route_routes.py
│   │       ├── order_routes.py
│   │       ├── order_group_routes.py
│   │       ├── optimization_routes.py
│   │       └── job_routes.py
│   ├── database/
│   │   ├── database.py
│   │   └── models.py
│   └── ...
└── requirements.txt
```

## Features

- FastAPI-based REST API
- Modular route registration
- SQLAlchemy ORM integration
- Automatic table creation through metadata sync
- Cross-origin support for frontend access
- Domain modules for logistics and optimization workflows

## Prerequisites

Before running the project, make sure you have:

- Python 3.10 or newer
- pip installed
- A configured database backend supported by your SQLAlchemy engine
- Environment variables set for database connectivity and application settings

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd TMS-Backend
```

2. Create a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root

## Running the Application

Start the FastAPI development server with:

```bash
uvicorn main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

## API Documentation

FastAPI provides built-in interactive docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Notes on the Current App Configuration

In `main.py`, the app:

- Creates a FastAPI instance with a descriptive title
- Enables CORS for development using `allow_origins=["*"]`
- Creates database tables automatically using SQLAlchemy metadata
- Includes all major route modules for the TMS domain

## Development Notes

- CORS is currently configured permissively for development convenience.
- Database tables are created automatically when the application starts through `models.Base.metadata.create_all(bind=engine)`.
- The project is structured for modular expansion as new logistics features are added.
