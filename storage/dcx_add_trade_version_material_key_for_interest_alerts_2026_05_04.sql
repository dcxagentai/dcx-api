-- DCX MVP trade interest alert material keys.
-- Run after dcx_add_trade_interest_alert_preferences_2026_05_03.sql.
--
-- This patch gives each trade version an explicit commodity/material key for matching
-- interested-trade alerts. Free-text material names remain available for descriptive
-- trade terms, while this field carries the simple alert taxonomy key.

ALTER TABLE public.stephen_dcx_trade_versions
ADD COLUMN IF NOT EXISTS normalized_material_key text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS stephen_dcx_trade_versions_normalized_material_key_idx
ON public.stephen_dcx_trade_versions(normalized_material_key)
WHERE normalized_material_key <> '';

UPDATE public.stephen_dcx_trade_versions
SET normalized_material_key = CASE
    WHEN normalized_material_name ~* '(^|\W)(aluminium|aluminum|primary aluminum|primary aluminium|aluminum ingot|aluminium ingot|p1020a)(\W|$)' THEN 'aluminum'
    WHEN normalized_material_name ~* '(^|\W)(wheat|milling wheat|feed wheat|durum)(\W|$)' THEN 'wheat'
    WHEN normalized_material_name ~* '(^|\W)(urea|fertilizer urea|fertiliser urea|prilled urea|granular urea)(\W|$)' THEN 'urea'
    WHEN normalized_material_name ~* '(^|\W)(copper|copper cathode|copper concentrate)(\W|$)' THEN 'copper'
    WHEN normalized_material_name ~* '(^|\W)(livestock|cattle|cow|cows|calves|dairy cattle)(\W|$)' THEN 'livestock'
    WHEN normalized_material_name ~* '(^|\W)(crude|crude oil|brent|wti)(\W|$)' THEN 'crude_oil'
    WHEN normalized_material_name ~* '(^|\W)(lng|liquefied natural gas|natural gas)(\W|$)' THEN 'lng'
    WHEN normalized_material_name ~* '(^|\W)(sugar|raw sugar|white sugar|icumsa)(\W|$)' THEN 'sugar'
    WHEN normalized_material_name ~* '(^|\W)(coffee|arabica|robusta)(\W|$)' THEN 'coffee'
    WHEN normalized_material_name ~* '(^|\W)(soybean|soybeans|soya|soy meal|soybean meal)(\W|$)' THEN 'soybeans'
    ELSE normalized_material_key
END
WHERE normalized_material_key = ''
  AND normalized_material_name <> '';
