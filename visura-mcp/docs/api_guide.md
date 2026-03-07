# Visura API & SISTER Guide for Agents

This guide helps you understand how the Italian Cadastral system (SISTER) works and how to use the Visura API tools effectively.

## Core Concepts

### Cadastral Identifiers
- **Provincia (Province)**: The administrative province (e.g., ROMA, MILANO). Usually 2 or 4 characters or the full name.
- **Comune (Municipality)**: The specific town.
- **Foglio (Sheet)**: A portion of the municipal territory. Always required.
- **Particella (Parcel)**: A specific plot of land or external perimeter of a building. Always required.
- **Subalterno (Sub-unit)**: Required for **Fabbricati** (Buildings) to identify a specific apartment or office. NOT used for **Terreni** (Land).
- **Sezione (Section)**: Some municipalities are divided into sections (e.g., 'A', 'B'). Use if known, otherwise omit.

### Search Types
1. **Terreni (T)**: Search for land. Returns owners (intestati) directly in the visura result.
2. **Fabbricati (F)**: Search for buildings. If you look for a parcel with many subalterni, you might receive a list of properties. You then need to use `request_intestati` with a specific `subalterno` to get the owners.

## Multi-step Journey
1. **Initial Search**: Use `request_visura` with `tipo_catasto=None` to check both Land and Buildings if you are unsure.
2. **Check Status**: Use `get_visura_result` until success.
3. **Parse Results**:
   - If `tipo_catasto='T'`, you usually have everything.
   - If `tipo_catasto='F'`, check if you need a specific `subalterno`.
4. **Owner Search**: If owners are missing for a building unit, use `request_intestati`.

## Common Pitfalls
- **Province Names**: Ensure you use the standard Italian name.
- **Session Timeout**: The system might take a few seconds to process. Always poll `get_visura_result`.
