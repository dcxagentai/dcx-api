-- CONTEXT:
-- Seeds the multilingual UX-string rows for the first authenticated DCX app WhatsApp
-- phone-link flow.
-- It exists so the new account-page phone linking controls and confirmed badges render
-- through the shared `stephen_dcx_ux_strings` model in English, Spanish, French, and German.
--
-- FLOW/SYSTEM:
-- - `app_account_page`
-- - `authenticated user links phone via WhatsApp OTP`
--
-- CONTRACT:
-- - Safe to rerun.
-- - Inserts missing English live originals only.
-- - Inserts missing live translations only.
-- - Does not delete or overwrite existing live rows.

WITH desired_english_originals(string_group, string_key, text_value) AS (
    VALUES
        ('app_account_page', 'field_primary_phone_code', $$WhatsApp code$$),
        ('app_account_page', 'field_phone_whatsapp_hint', $$Link a WhatsApp number to route messages into this DCX account.$$),
        ('app_account_page', 'field_phone_whatsapp_code_hint', $$Enter the six-digit code sent to WhatsApp.$$),
        ('app_account_page', 'field_phone_send_code', $$Send code$$),
        ('app_account_page', 'field_phone_resend_code', $$Resend code$$),
        ('app_account_page', 'field_phone_verify_code', $$Verify$$),
        ('app_account_page', 'field_phone_confirmed_badge', $$Verified$$),
        ('app_account_page', 'field_email_confirmed_badge', $$Verified$$),
        ('app_account_page', 'field_phone_pending_status', $$Waiting for code$$)
),
english_language AS (
    SELECT id
    FROM stephen_dcx_languages
    WHERE language_code = 'en'
    LIMIT 1
)
INSERT INTO stephen_dcx_ux_strings
(string_group, string_key, language_id, text, is_original, is_live, version_of_id, translation_of_id)
SELECT
    desired_english_originals.string_group,
    desired_english_originals.string_key,
    english_language.id,
    desired_english_originals.text_value,
    TRUE,
    TRUE,
    NULL,
    NULL
FROM desired_english_originals
CROSS JOIN english_language
WHERE NOT EXISTS (
    SELECT 1
    FROM stephen_dcx_ux_strings existing
    WHERE existing.string_group = desired_english_originals.string_group
      AND existing.string_key = desired_english_originals.string_key
      AND existing.language_id = english_language.id
      AND existing.is_original = TRUE
      AND existing.is_live = TRUE
);

WITH desired_translations(string_group, string_key, language_code, text_value) AS (
    VALUES
        ('app_account_page', 'field_primary_phone_code', 'es', $$Código de WhatsApp$$),
        ('app_account_page', 'field_primary_phone_code', 'fr', $$Code WhatsApp$$),
        ('app_account_page', 'field_primary_phone_code', 'de', $$WhatsApp-Code$$),

        ('app_account_page', 'field_phone_whatsapp_hint', 'es', $$Vincula un número de WhatsApp para dirigir los mensajes a esta cuenta de DCX.$$),
        ('app_account_page', 'field_phone_whatsapp_hint', 'fr', $$Associez un numéro WhatsApp pour acheminer les messages vers ce compte DCX.$$),
        ('app_account_page', 'field_phone_whatsapp_hint', 'de', $$Verknüpfen Sie eine WhatsApp-Nummer, um Nachrichten in dieses DCX-Konto zu leiten.$$),

        ('app_account_page', 'field_phone_whatsapp_code_hint', 'es', $$Introduce el código de seis dígitos enviado por WhatsApp.$$),
        ('app_account_page', 'field_phone_whatsapp_code_hint', 'fr', $$Entrez le code à six chiffres envoyé par WhatsApp.$$),
        ('app_account_page', 'field_phone_whatsapp_code_hint', 'de', $$Geben Sie den sechsstelligen Code ein, der per WhatsApp gesendet wurde.$$),

        ('app_account_page', 'field_phone_send_code', 'es', $$Enviar código$$),
        ('app_account_page', 'field_phone_send_code', 'fr', $$Envoyer le code$$),
        ('app_account_page', 'field_phone_send_code', 'de', $$Code senden$$),

        ('app_account_page', 'field_phone_resend_code', 'es', $$Reenviar código$$),
        ('app_account_page', 'field_phone_resend_code', 'fr', $$Renvoyer le code$$),
        ('app_account_page', 'field_phone_resend_code', 'de', $$Code erneut senden$$),

        ('app_account_page', 'field_phone_verify_code', 'es', $$Verificar$$),
        ('app_account_page', 'field_phone_verify_code', 'fr', $$Vérifier$$),
        ('app_account_page', 'field_phone_verify_code', 'de', $$Verifizieren$$),

        ('app_account_page', 'field_phone_confirmed_badge', 'es', $$Verificado$$),
        ('app_account_page', 'field_phone_confirmed_badge', 'fr', $$Vérifié$$),
        ('app_account_page', 'field_phone_confirmed_badge', 'de', $$Verifiziert$$),

        ('app_account_page', 'field_email_confirmed_badge', 'es', $$Verificado$$),
        ('app_account_page', 'field_email_confirmed_badge', 'fr', $$Vérifié$$),
        ('app_account_page', 'field_email_confirmed_badge', 'de', $$Verifiziert$$),

        ('app_account_page', 'field_phone_pending_status', 'es', $$Esperando código$$),
        ('app_account_page', 'field_phone_pending_status', 'fr', $$En attente du code$$),
        ('app_account_page', 'field_phone_pending_status', 'de', $$Warten auf Code$$)
),
language_rows AS (
    SELECT id, language_code
    FROM stephen_dcx_languages
    WHERE language_code IN ('en', 'es', 'fr', 'de')
),
english_live_originals AS (
    SELECT
        originals.id,
        originals.string_group,
        originals.string_key
    FROM stephen_dcx_ux_strings originals
    JOIN language_rows english_language
      ON english_language.id = originals.language_id
     AND english_language.language_code = 'en'
    WHERE originals.is_original = TRUE
      AND originals.is_live = TRUE
)
INSERT INTO stephen_dcx_ux_strings
(string_group, string_key, language_id, text, is_original, is_live, version_of_id, translation_of_id)
SELECT
    desired_translations.string_group,
    desired_translations.string_key,
    target_language.id,
    desired_translations.text_value,
    FALSE,
    TRUE,
    NULL,
    english_live_originals.id
FROM desired_translations
JOIN language_rows target_language
  ON target_language.language_code = desired_translations.language_code
JOIN english_live_originals
  ON english_live_originals.string_group = desired_translations.string_group
 AND english_live_originals.string_key = desired_translations.string_key
WHERE NOT EXISTS (
    SELECT 1
    FROM stephen_dcx_ux_strings existing
    WHERE existing.string_group = desired_translations.string_group
      AND existing.string_key = desired_translations.string_key
      AND existing.language_id = target_language.id
      AND existing.is_live = TRUE
);
