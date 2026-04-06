-- Migration: Add profile columns to user_profiles
-- Run this in Supabase Dashboard → SQL Editor

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS full_name TEXT,
  ADD COLUMN IF NOT EXISTS nickname  TEXT,
  ADD COLUMN IF NOT EXISTS birthday  TEXT;
