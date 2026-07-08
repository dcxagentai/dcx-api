# Content Page Public Route Paths Added To Admin Detail

The admin content-page detail capability now includes `category_slug` and `public_route_path` on each `translation_summary.existing_translations` row. The route path uses the localized category slug when a live localized category exists and falls back to the original category slug otherwise.

This supports the admin editor's public-route link strip without requiring the frontend to guess whether a category has been translated. The adjacent page-detail test now asserts the fallback route path shape.
