-- Supabase Schema Migration: Initial Setup
-- This script sets up the core tables for the query-mind platform.
-- Run this in your Supabase SQL Editor.

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Migrations Tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Database Connections
CREATE TABLE IF NOT EXISTS database_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    db_type TEXT NOT NULL, -- postgresql, mysql, sqlite
    host TEXT,
    port INTEGER,
    database TEXT NOT NULL,
    username TEXT,
    password TEXT, -- Note: Store encrypted in production
    ssl_mode TEXT DEFAULT 'disable',
    readonly BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for Connections
ALTER TABLE database_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own connections" 
ON database_connections 
FOR ALL 
USING (auth.uid() = owner_id);

-- 4. Dashboards
CREATE TABLE IF NOT EXISTS dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    icon TEXT DEFAULT '📊',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for Dashboards
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own dashboards" 
ON dashboards 
FOR ALL 
USING (auth.uid() = owner_id);

-- 5. Dashboard Widgets
CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dashboard_id UUID NOT NULL REFERENCES dashboards(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES database_connections(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    viz_type TEXT NOT NULL, -- bar, line, donut, table, kpi
    size TEXT DEFAULT 'half',
    sql TEXT,
    chart_config JSONB DEFAULT '{}',
    layout_params JSONB DEFAULT '{}', -- x, y, w, h
    cadence TEXT DEFAULT 'Manual only',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for Widgets
ALTER TABLE dashboard_widgets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own widgets" 
ON dashboard_widgets 
FOR ALL 
USING (auth.uid() = owner_id);

-- 6. Saved Queries
CREATE TABLE IF NOT EXISTS saved_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    connection_id UUID REFERENCES database_connections(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    sql TEXT NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}', -- tags, folder_name, icon
    schedule JSONB DEFAULT '{}', -- frequency, time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for Saved Queries
ALTER TABLE saved_queries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own queries" 
ON saved_queries 
FOR ALL 
USING (auth.uid() = owner_id);

-- Log Initial Migration
INSERT INTO schema_migrations (name) VALUES ('001_initial_schema');
