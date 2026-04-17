The app now has a real backend-backed countries reference path instead of relying on a frontend-only embedded list.

This slice added a reusable countries domain capability and route:
- `countries/read_active_dcx_reference_countries_bundle.py`
- `routes/public/dcx_api_routes_public_reference_countries_bundle.py`

It also added the schema/seed SQL file:
- `storage/dcx_add_countries_reference_tables_2026_04_17.sql`

The tables are:
- `stephen_dcx_countries`
- `stephen_dcx_country_calling_codes`

The current app phone-country combobox is the first consumer of this countries bundle. The frontend now reads `/public/reference/countries-bundle`, flattens the nested country + calling-code rows into phone-country options, and still uses E.164 as the real contact-method source of truth. That keeps the countries tables as display/business metadata rather than phone-identity truth.

The app still handles ambiguous shared calling codes honestly. If one calling code belongs to multiple countries, display can fall back instead of pretending one exact country can always be inferred from the phone number alone.
