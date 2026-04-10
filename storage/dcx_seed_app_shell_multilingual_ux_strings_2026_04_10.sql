-- CONTEXT:
-- Seeds the additional multilingual UX-string rows for the refreshed authenticated DCX app shell.
-- It exists so the new shadcn-based sidebar, lower user popup, page titles, and compact field
-- state labels render through the shared `stephen_dcx_ux_strings` model in English, Spanish,
-- French, and German.
--
-- FLOW/SYSTEM:
-- - `app_account_page`
--
-- CONTRACT:
-- - Safe to rerun.
-- - Inserts missing English live originals only.
-- - Inserts missing live translations only.
-- - Does not delete or overwrite existing live rows.

WITH desired_english_originals(string_group, string_key, text_value) AS (
    VALUES
        ('app_account_page', 'page_title_account', $$Account$$),
        ('app_account_page', 'page_title_settings', $$Settings$$),
        ('app_account_page', 'page_title_activity_log', $$Activity Log$$),
        ('app_account_page', 'nav_group_workspace', $$Workspace$$),
        ('app_account_page', 'nav_chats', $$Chats$$),
        ('app_account_page', 'nav_chats_inbox', $$Inbox$$),
        ('app_account_page', 'nav_chats_humans', $$Humans$$),
        ('app_account_page', 'nav_chats_agents', $$Agents$$),
        ('app_account_page', 'nav_trades', $$Trades$$),
        ('app_account_page', 'nav_trades_market_watch', $$Market Watch$$),
        ('app_account_page', 'nav_trades_my_trades', $$My Trades$$),
        ('app_account_page', 'nav_contacts', $$Contacts$$),
        ('app_account_page', 'nav_files', $$Files$$),
        ('app_account_page', 'nav_files_documents', $$Documents$$),
        ('app_account_page', 'nav_files_images', $$Images$$),
        ('app_account_page', 'nav_files_audio', $$Audio$$),
        ('app_account_page', 'nav_badge_soon', $$Soon$$),
        ('app_account_page', 'nav_toggle_section', $$Toggle section$$),
        ('app_account_page', 'nav_admin_workspace', $$Admin workspace$$),
        ('app_account_page', 'user_menu_account', $$Account$$),
        ('app_account_page', 'user_menu_subscription', $$Subscription$$),
        ('app_account_page', 'user_menu_settings', $$Settings$$),
        ('app_account_page', 'user_menu_privacy_security', $$Privacy & Security$$),
        ('app_account_page', 'user_menu_activity_log', $$Activity Log$$),
        ('app_account_page', 'user_menu_log_out', $$Log out$$),
        ('app_account_page', 'user_menu_log_out_pending', $$Signing out...$$),
        ('app_account_page', 'settings_eyebrow', $$Settings$$),
        ('app_account_page', 'settings_title', $$Preferences and notifications$$),
        ('app_account_page', 'settings_subtitle', $$Control language, timezone, and announcement preferences from one simple settings page.$$),
        ('app_account_page', 'activity_subtitle', $$See the basic account events we are already recording for this user.$$),
        ('app_account_page', 'editable_status_compact_idle', $$Editable$$),
        ('app_account_page', 'editable_status_compact_changed_unsaved', $$Changed, unsaved$$),
        ('app_account_page', 'editable_status_compact_saved', $$Saved$$),
        ('app_account_page', 'editable_status_compact_save_failed', $$Save failed$$)
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
        ('app_account_page', 'page_title_account', 'es', $$Cuenta$$),
        ('app_account_page', 'page_title_account', 'fr', $$Compte$$),
        ('app_account_page', 'page_title_account', 'de', $$Konto$$),
        ('app_account_page', 'page_title_settings', 'es', $$Configuración$$),
        ('app_account_page', 'page_title_settings', 'fr', $$Paramètres$$),
        ('app_account_page', 'page_title_settings', 'de', $$Einstellungen$$),
        ('app_account_page', 'page_title_activity_log', 'es', $$Registro de actividad$$),
        ('app_account_page', 'page_title_activity_log', 'fr', $$Journal d'activité$$),
        ('app_account_page', 'page_title_activity_log', 'de', $$Aktivitätsprotokoll$$),
        ('app_account_page', 'nav_group_workspace', 'es', $$Espacio de trabajo$$),
        ('app_account_page', 'nav_group_workspace', 'fr', $$Espace de travail$$),
        ('app_account_page', 'nav_group_workspace', 'de', $$Arbeitsbereich$$),
        ('app_account_page', 'nav_chats', 'es', $$Chats$$),
        ('app_account_page', 'nav_chats', 'fr', $$Discussions$$),
        ('app_account_page', 'nav_chats', 'de', $$Chats$$),
        ('app_account_page', 'nav_chats_inbox', 'es', $$Bandeja de entrada$$),
        ('app_account_page', 'nav_chats_inbox', 'fr', $$Boîte de réception$$),
        ('app_account_page', 'nav_chats_inbox', 'de', $$Posteingang$$),
        ('app_account_page', 'nav_chats_humans', 'es', $$Personas$$),
        ('app_account_page', 'nav_chats_humans', 'fr', $$Humains$$),
        ('app_account_page', 'nav_chats_humans', 'de', $$Menschen$$),
        ('app_account_page', 'nav_chats_agents', 'es', $$Agentes$$),
        ('app_account_page', 'nav_chats_agents', 'fr', $$Agents$$),
        ('app_account_page', 'nav_chats_agents', 'de', $$Agenten$$),
        ('app_account_page', 'nav_trades', 'es', $$Operaciones$$),
        ('app_account_page', 'nav_trades', 'fr', $$Transactions$$),
        ('app_account_page', 'nav_trades', 'de', $$Geschäfte$$),
        ('app_account_page', 'nav_trades_market_watch', 'es', $$Vigilancia de mercado$$),
        ('app_account_page', 'nav_trades_market_watch', 'fr', $$Veille de marché$$),
        ('app_account_page', 'nav_trades_market_watch', 'de', $$Marktbeobachtung$$),
        ('app_account_page', 'nav_trades_my_trades', 'es', $$Mis operaciones$$),
        ('app_account_page', 'nav_trades_my_trades', 'fr', $$Mes transactions$$),
        ('app_account_page', 'nav_trades_my_trades', 'de', $$Meine Geschäfte$$),
        ('app_account_page', 'nav_contacts', 'es', $$Contactos$$),
        ('app_account_page', 'nav_contacts', 'fr', $$Contacts$$),
        ('app_account_page', 'nav_contacts', 'de', $$Kontakte$$),
        ('app_account_page', 'nav_files', 'es', $$Archivos$$),
        ('app_account_page', 'nav_files', 'fr', $$Fichiers$$),
        ('app_account_page', 'nav_files', 'de', $$Dateien$$),
        ('app_account_page', 'nav_files_documents', 'es', $$Documentos$$),
        ('app_account_page', 'nav_files_documents', 'fr', $$Documents$$),
        ('app_account_page', 'nav_files_documents', 'de', $$Dokumente$$),
        ('app_account_page', 'nav_files_images', 'es', $$Imágenes$$),
        ('app_account_page', 'nav_files_images', 'fr', $$Images$$),
        ('app_account_page', 'nav_files_images', 'de', $$Bilder$$),
        ('app_account_page', 'nav_files_audio', 'es', $$Audio$$),
        ('app_account_page', 'nav_files_audio', 'fr', $$Audio$$),
        ('app_account_page', 'nav_files_audio', 'de', $$Audio$$),
        ('app_account_page', 'nav_badge_soon', 'es', $$Pronto$$),
        ('app_account_page', 'nav_badge_soon', 'fr', $$Bientôt$$),
        ('app_account_page', 'nav_badge_soon', 'de', $$Bald$$),
        ('app_account_page', 'nav_toggle_section', 'es', $$Alternar sección$$),
        ('app_account_page', 'nav_toggle_section', 'fr', $$Basculer la section$$),
        ('app_account_page', 'nav_toggle_section', 'de', $$Bereich umschalten$$),
        ('app_account_page', 'nav_admin_workspace', 'es', $$Espacio admin$$),
        ('app_account_page', 'nav_admin_workspace', 'fr', $$Espace admin$$),
        ('app_account_page', 'nav_admin_workspace', 'de', $$Admin-Bereich$$),
        ('app_account_page', 'user_menu_account', 'es', $$Cuenta$$),
        ('app_account_page', 'user_menu_account', 'fr', $$Compte$$),
        ('app_account_page', 'user_menu_account', 'de', $$Konto$$),
        ('app_account_page', 'user_menu_subscription', 'es', $$Suscripción$$),
        ('app_account_page', 'user_menu_subscription', 'fr', $$Abonnement$$),
        ('app_account_page', 'user_menu_subscription', 'de', $$Abonnement$$),
        ('app_account_page', 'user_menu_settings', 'es', $$Configuración$$),
        ('app_account_page', 'user_menu_settings', 'fr', $$Paramètres$$),
        ('app_account_page', 'user_menu_settings', 'de', $$Einstellungen$$),
        ('app_account_page', 'user_menu_privacy_security', 'es', $$Privacidad y seguridad$$),
        ('app_account_page', 'user_menu_privacy_security', 'fr', $$Confidentialité et sécurité$$),
        ('app_account_page', 'user_menu_privacy_security', 'de', $$Datenschutz & Sicherheit$$),
        ('app_account_page', 'user_menu_activity_log', 'es', $$Registro de actividad$$),
        ('app_account_page', 'user_menu_activity_log', 'fr', $$Journal d'activité$$),
        ('app_account_page', 'user_menu_activity_log', 'de', $$Aktivitätsprotokoll$$),
        ('app_account_page', 'user_menu_log_out', 'es', $$Cerrar sesión$$),
        ('app_account_page', 'user_menu_log_out', 'fr', $$Se déconnecter$$),
        ('app_account_page', 'user_menu_log_out', 'de', $$Abmelden$$),
        ('app_account_page', 'user_menu_log_out_pending', 'es', $$Cerrando sesión...$$),
        ('app_account_page', 'user_menu_log_out_pending', 'fr', $$Déconnexion en cours...$$),
        ('app_account_page', 'user_menu_log_out_pending', 'de', $$Abmeldung läuft...$$),
        ('app_account_page', 'settings_eyebrow', 'es', $$Configuración$$),
        ('app_account_page', 'settings_eyebrow', 'fr', $$Paramètres$$),
        ('app_account_page', 'settings_eyebrow', 'de', $$Einstellungen$$),
        ('app_account_page', 'settings_title', 'es', $$Preferencias y notificaciones$$),
        ('app_account_page', 'settings_title', 'fr', $$Préférences et notifications$$),
        ('app_account_page', 'settings_title', 'de', $$Einstellungen und Benachrichtigungen$$),
        ('app_account_page', 'settings_subtitle', 'es', $$Controla el idioma, la zona horaria y las preferencias de anuncios desde una sola página sencilla de configuración.$$),
        ('app_account_page', 'settings_subtitle', 'fr', $$Contrôlez la langue, le fuseau horaire et les préférences d'annonces depuis une page de paramètres simple.$$),
        ('app_account_page', 'settings_subtitle', 'de', $$Steuern Sie Sprache, Zeitzone und Mitteilungspräferenzen über eine einfache Einstellungsseite.$$),
        ('app_account_page', 'activity_subtitle', 'es', $$Consulta los eventos básicos de la cuenta que ya estamos registrando para este usuario.$$),
        ('app_account_page', 'activity_subtitle', 'fr', $$Consultez les événements de base du compte que nous enregistrons déjà pour cet utilisateur.$$),
        ('app_account_page', 'activity_subtitle', 'de', $$Sehen Sie die grundlegenden Kontoereignisse, die wir bereits für diesen Benutzer protokollieren.$$),
        ('app_account_page', 'editable_status_compact_idle', 'es', $$Editable$$),
        ('app_account_page', 'editable_status_compact_idle', 'fr', $$Modifiable$$),
        ('app_account_page', 'editable_status_compact_idle', 'de', $$Bearbeitbar$$),
        ('app_account_page', 'editable_status_compact_changed_unsaved', 'es', $$Cambiado, sin guardar$$),
        ('app_account_page', 'editable_status_compact_changed_unsaved', 'fr', $$Modifié, non enregistré$$),
        ('app_account_page', 'editable_status_compact_changed_unsaved', 'de', $$Geändert, ungespeichert$$),
        ('app_account_page', 'editable_status_compact_saved', 'es', $$Guardado$$),
        ('app_account_page', 'editable_status_compact_saved', 'fr', $$Enregistré$$),
        ('app_account_page', 'editable_status_compact_saved', 'de', $$Gespeichert$$),
        ('app_account_page', 'editable_status_compact_save_failed', 'es', $$Error al guardar$$),
        ('app_account_page', 'editable_status_compact_save_failed', 'fr', $$Échec de l'enregistrement$$),
        ('app_account_page', 'editable_status_compact_save_failed', 'de', $$Speichern fehlgeschlagen$$)
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
