-- CONTEXT:
-- Seeds and updates the multilingual UX strings for the authenticated DCX app
-- Messages and Send slice.
--
-- It exists so the now-polished user-facing inbox, detail panel, filters, and
-- compose surface render through the shared `stephen_dcx_ux_strings` model in
-- the MVP languages instead of falling back to repo defaults.
--
-- FLOW/SYSTEM:
-- - `app_account_page`
-- - authenticated DCX app: Messages + Send
--
-- CONTRACT:
-- - Safe to rerun.
-- - Updates existing live rows for the targeted keys in English, Spanish,
--   French, and German.
-- - Inserts missing live rows for those same keys.
-- - Does not delete rows.
-- - Keeps English live originals as the translation anchor.

WITH desired_strings(string_group, string_key, language_code, text_value, is_original) AS (
    VALUES
        ('app_account_page', 'page_title_messages', 'en', $$Messages$$, TRUE),
        ('app_account_page', 'page_title_messages', 'es', $$Mensajes$$, FALSE),
        ('app_account_page', 'page_title_messages', 'fr', $$Messages$$, FALSE),
        ('app_account_page', 'page_title_messages', 'de', $$Nachrichten$$, FALSE),

        ('app_account_page', 'page_title_send', 'en', $$Send$$, TRUE),
        ('app_account_page', 'page_title_send', 'es', $$Enviar$$, FALSE),
        ('app_account_page', 'page_title_send', 'fr', $$Envoyer$$, FALSE),
        ('app_account_page', 'page_title_send', 'de', $$Senden$$, FALSE),

        ('app_account_page', 'nav_messages', 'en', $$Messages$$, TRUE),
        ('app_account_page', 'nav_messages', 'es', $$Mensajes$$, FALSE),
        ('app_account_page', 'nav_messages', 'fr', $$Messages$$, FALSE),
        ('app_account_page', 'nav_messages', 'de', $$Nachrichten$$, FALSE),

        ('app_account_page', 'nav_send', 'en', $$Send$$, TRUE),
        ('app_account_page', 'nav_send', 'es', $$Enviar$$, FALSE),
        ('app_account_page', 'nav_send', 'fr', $$Envoyer$$, FALSE),
        ('app_account_page', 'nav_send', 'de', $$Senden$$, FALSE),

        ('app_account_page', 'nav_messages_text', 'en', $$Text$$, TRUE),
        ('app_account_page', 'nav_messages_text', 'es', $$Texto$$, FALSE),
        ('app_account_page', 'nav_messages_text', 'fr', $$Texte$$, FALSE),
        ('app_account_page', 'nav_messages_text', 'de', $$Text$$, FALSE),

        ('app_account_page', 'nav_messages_images', 'en', $$Images$$, TRUE),
        ('app_account_page', 'nav_messages_images', 'es', $$Imágenes$$, FALSE),
        ('app_account_page', 'nav_messages_images', 'fr', $$Images$$, FALSE),
        ('app_account_page', 'nav_messages_images', 'de', $$Bilder$$, FALSE),

        ('app_account_page', 'nav_messages_audio', 'en', $$Audio$$, TRUE),
        ('app_account_page', 'nav_messages_audio', 'es', $$Audio$$, FALSE),
        ('app_account_page', 'nav_messages_audio', 'fr', $$Audio$$, FALSE),
        ('app_account_page', 'nav_messages_audio', 'de', $$Audio$$, FALSE),

        ('app_account_page', 'nav_messages_documents', 'en', $$Documents$$, TRUE),
        ('app_account_page', 'nav_messages_documents', 'es', $$Documentos$$, FALSE),
        ('app_account_page', 'nav_messages_documents', 'fr', $$Documents$$, FALSE),
        ('app_account_page', 'nav_messages_documents', 'de', $$Dokumente$$, FALSE),

        ('app_account_page', 'messages_eyebrow', 'en', $$Messages$$, TRUE),
        ('app_account_page', 'messages_eyebrow', 'es', $$Mensajes$$, FALSE),
        ('app_account_page', 'messages_eyebrow', 'fr', $$Messages$$, FALSE),
        ('app_account_page', 'messages_eyebrow', 'de', $$Nachrichten$$, FALSE),

        ('app_account_page', 'messages_title', 'en', $$Messages$$, TRUE),
        ('app_account_page', 'messages_title', 'es', $$Mensajes$$, FALSE),
        ('app_account_page', 'messages_title', 'fr', $$Messages$$, FALSE),
        ('app_account_page', 'messages_title', 'de', $$Nachrichten$$, FALSE),

        ('app_account_page', 'messages_subtitle', 'en', $$App, WhatsApp, and email messages in one inbox.$$ , TRUE),
        ('app_account_page', 'messages_subtitle', 'es', $$Mensajes de la app, WhatsApp y correo en una sola bandeja.$$ , FALSE),
        ('app_account_page', 'messages_subtitle', 'fr', $$Messages de l'application, WhatsApp et e-mail dans une seule boîte de réception.$$ , FALSE),
        ('app_account_page', 'messages_subtitle', 'de', $$App-, WhatsApp- und E-Mail-Nachrichten in einem Posteingang.$$ , FALSE),

        ('app_account_page', 'messages_filter_all', 'en', $$All formats$$, TRUE),
        ('app_account_page', 'messages_filter_all', 'es', $$Todos los formatos$$, FALSE),
        ('app_account_page', 'messages_filter_all', 'fr', $$Tous les formats$$, FALSE),
        ('app_account_page', 'messages_filter_all', 'de', $$Alle Formate$$, FALSE),

        ('app_account_page', 'messages_filter_text', 'en', $$Text$$, TRUE),
        ('app_account_page', 'messages_filter_text', 'es', $$Texto$$, FALSE),
        ('app_account_page', 'messages_filter_text', 'fr', $$Texte$$, FALSE),
        ('app_account_page', 'messages_filter_text', 'de', $$Text$$, FALSE),

        ('app_account_page', 'messages_filter_image', 'en', $$Images$$, TRUE),
        ('app_account_page', 'messages_filter_image', 'es', $$Imágenes$$, FALSE),
        ('app_account_page', 'messages_filter_image', 'fr', $$Images$$, FALSE),
        ('app_account_page', 'messages_filter_image', 'de', $$Bilder$$, FALSE),

        ('app_account_page', 'messages_filter_audio', 'en', $$Audio$$, TRUE),
        ('app_account_page', 'messages_filter_audio', 'es', $$Audio$$, FALSE),
        ('app_account_page', 'messages_filter_audio', 'fr', $$Audio$$, FALSE),
        ('app_account_page', 'messages_filter_audio', 'de', $$Audio$$, FALSE),

        ('app_account_page', 'messages_filter_document', 'en', $$Documents$$, TRUE),
        ('app_account_page', 'messages_filter_document', 'es', $$Documentos$$, FALSE),
        ('app_account_page', 'messages_filter_document', 'fr', $$Documents$$, FALSE),
        ('app_account_page', 'messages_filter_document', 'de', $$Dokumente$$, FALSE),

        ('app_account_page', 'messages_empty', 'en', $$No messages yet for this filter.$$ , TRUE),
        ('app_account_page', 'messages_empty', 'es', $$Todavía no hay mensajes para este filtro.$$ , FALSE),
        ('app_account_page', 'messages_empty', 'fr', $$Aucun message pour ce filtre pour le moment.$$ , FALSE),
        ('app_account_page', 'messages_empty', 'de', $$Für diesen Filter gibt es noch keine Nachrichten.$$ , FALSE),

        ('app_account_page', 'messages_loading', 'en', $$Loading messages...$$, TRUE),
        ('app_account_page', 'messages_loading', 'es', $$Cargando mensajes...$$, FALSE),
        ('app_account_page', 'messages_loading', 'fr', $$Chargement des messages...$$, FALSE),
        ('app_account_page', 'messages_loading', 'de', $$Nachrichten werden geladen...$$, FALSE),

        ('app_account_page', 'messages_error_title', 'en', $$We could not load the Messages inbox.$$ , TRUE),
        ('app_account_page', 'messages_error_title', 'es', $$No pudimos cargar la bandeja de Mensajes.$$ , FALSE),
        ('app_account_page', 'messages_error_title', 'fr', $$Nous n'avons pas pu charger la boîte Messages.$$ , FALSE),
        ('app_account_page', 'messages_error_title', 'de', $$Der Nachrichten-Posteingang konnte nicht geladen werden.$$ , FALSE),

        ('app_account_page', 'messages_error_suggested_action', 'en', $$Retry after confirming the backend and your session are still healthy.$$ , TRUE),
        ('app_account_page', 'messages_error_suggested_action', 'es', $$Reintenta después de confirmar que el backend y tu sesión siguen bien.$$ , FALSE),
        ('app_account_page', 'messages_error_suggested_action', 'fr', $$Réessayez après avoir confirmé que le backend et votre session fonctionnent toujours correctement.$$ , FALSE),
        ('app_account_page', 'messages_error_suggested_action', 'de', $$Versuchen Sie es erneut, nachdem Sie bestätigt haben, dass Backend und Sitzung weiterhin funktionieren.$$ , FALSE),

        ('app_account_page', 'messages_search_placeholder', 'en', $$Search messages...$$, TRUE),
        ('app_account_page', 'messages_search_placeholder', 'es', $$Buscar mensajes...$$, FALSE),
        ('app_account_page', 'messages_search_placeholder', 'fr', $$Rechercher des messages...$$, FALSE),
        ('app_account_page', 'messages_search_placeholder', 'de', $$Nachrichten durchsuchen...$$, FALSE),

        ('app_account_page', 'messages_identity_filter_all', 'en', $$All identities$$, TRUE),
        ('app_account_page', 'messages_identity_filter_all', 'es', $$Todas las identidades$$, FALSE),
        ('app_account_page', 'messages_identity_filter_all', 'fr', $$Toutes les identités$$, FALSE),
        ('app_account_page', 'messages_identity_filter_all', 'de', $$Alle Identitäten$$, FALSE),

        ('app_account_page', 'messages_language_filter_all', 'en', $$All languages$$, TRUE),
        ('app_account_page', 'messages_language_filter_all', 'es', $$Todos los idiomas$$, FALSE),
        ('app_account_page', 'messages_language_filter_all', 'fr', $$Toutes les langues$$, FALSE),
        ('app_account_page', 'messages_language_filter_all', 'de', $$Alle Sprachen$$, FALSE),

        ('app_account_page', 'messages_channel_filter_label', 'en', $$Channel$$, TRUE),
        ('app_account_page', 'messages_channel_filter_label', 'es', $$Canal$$, FALSE),
        ('app_account_page', 'messages_channel_filter_label', 'fr', $$Canal$$, FALSE),
        ('app_account_page', 'messages_channel_filter_label', 'de', $$Kanal$$, FALSE),

        ('app_account_page', 'messages_channel_filter_all', 'en', $$All channels$$, TRUE),
        ('app_account_page', 'messages_channel_filter_all', 'es', $$Todos los canales$$, FALSE),
        ('app_account_page', 'messages_channel_filter_all', 'fr', $$Tous les canaux$$, FALSE),
        ('app_account_page', 'messages_channel_filter_all', 'de', $$Alle Kanäle$$, FALSE),

        ('app_account_page', 'messages_channel_filter_app', 'en', $$Web app$$, TRUE),
        ('app_account_page', 'messages_channel_filter_app', 'es', $$Aplicación web$$, FALSE),
        ('app_account_page', 'messages_channel_filter_app', 'fr', $$Application web$$, FALSE),
        ('app_account_page', 'messages_channel_filter_app', 'de', $$Web-App$$, FALSE),

        ('app_account_page', 'messages_channel_filter_whatsapp', 'en', $$WhatsApp$$, TRUE),
        ('app_account_page', 'messages_channel_filter_whatsapp', 'es', $$WhatsApp$$, FALSE),
        ('app_account_page', 'messages_channel_filter_whatsapp', 'fr', $$WhatsApp$$, FALSE),
        ('app_account_page', 'messages_channel_filter_whatsapp', 'de', $$WhatsApp$$, FALSE),

        ('app_account_page', 'messages_channel_filter_email', 'en', $$Email$$, TRUE),
        ('app_account_page', 'messages_channel_filter_email', 'es', $$Correo$$, FALSE),
        ('app_account_page', 'messages_channel_filter_email', 'fr', $$E-mail$$, FALSE),
        ('app_account_page', 'messages_channel_filter_email', 'de', $$E-Mail$$, FALSE),

        ('app_account_page', 'messages_compose_label', 'en', $$New message$$, TRUE),
        ('app_account_page', 'messages_compose_label', 'es', $$Nuevo mensaje$$, FALSE),
        ('app_account_page', 'messages_compose_label', 'fr', $$Nouveau message$$, FALSE),
        ('app_account_page', 'messages_compose_label', 'de', $$Neue Nachricht$$, FALSE),

        ('app_account_page', 'messages_compose_placeholder', 'en', $$Send a message, photo, voice note, or document to DCX.$$ , TRUE),
        ('app_account_page', 'messages_compose_placeholder', 'es', $$Envía un mensaje, foto, nota de voz o documento a DCX.$$ , FALSE),
        ('app_account_page', 'messages_compose_placeholder', 'fr', $$Envoyez un message, une photo, une note vocale ou un document à DCX.$$ , FALSE),
        ('app_account_page', 'messages_compose_placeholder', 'de', $$Senden Sie eine Nachricht, ein Foto, eine Sprachnotiz oder ein Dokument an DCX.$$ , FALSE),

        ('app_account_page', 'messages_compose_files_label', 'en', $$Attach files$$, TRUE),
        ('app_account_page', 'messages_compose_files_label', 'es', $$Adjuntar archivos$$, FALSE),
        ('app_account_page', 'messages_compose_files_label', 'fr', $$Joindre des fichiers$$, FALSE),
        ('app_account_page', 'messages_compose_files_label', 'de', $$Dateien anhängen$$, FALSE),

        ('app_account_page', 'messages_compose_files_selected', 'en', $$Selected files$$, TRUE),
        ('app_account_page', 'messages_compose_files_selected', 'es', $$Archivos seleccionados$$, FALSE),
        ('app_account_page', 'messages_compose_files_selected', 'fr', $$Fichiers sélectionnés$$, FALSE),
        ('app_account_page', 'messages_compose_files_selected', 'de', $$Ausgewählte Dateien$$, FALSE),

        ('app_account_page', 'messages_compose_files_count_singular', 'en', $$file$$, TRUE),
        ('app_account_page', 'messages_compose_files_count_singular', 'es', $$archivo$$, FALSE),
        ('app_account_page', 'messages_compose_files_count_singular', 'fr', $$fichier$$, FALSE),
        ('app_account_page', 'messages_compose_files_count_singular', 'de', $$Datei$$, FALSE),

        ('app_account_page', 'messages_compose_files_count_plural', 'en', $$files$$, TRUE),
        ('app_account_page', 'messages_compose_files_count_plural', 'es', $$archivos$$, FALSE),
        ('app_account_page', 'messages_compose_files_count_plural', 'fr', $$fichiers$$, FALSE),
        ('app_account_page', 'messages_compose_files_count_plural', 'de', $$Dateien$$, FALSE),

        ('app_account_page', 'messages_compose_submit_idle', 'en', $$Send message$$, TRUE),
        ('app_account_page', 'messages_compose_submit_idle', 'es', $$Enviar mensaje$$, FALSE),
        ('app_account_page', 'messages_compose_submit_idle', 'fr', $$Envoyer le message$$, FALSE),
        ('app_account_page', 'messages_compose_submit_idle', 'de', $$Nachricht senden$$, FALSE),

        ('app_account_page', 'messages_compose_submit_pending', 'en', $$Sending...$$, TRUE),
        ('app_account_page', 'messages_compose_submit_pending', 'es', $$Enviando...$$, FALSE),
        ('app_account_page', 'messages_compose_submit_pending', 'fr', $$Envoi en cours...$$, FALSE),
        ('app_account_page', 'messages_compose_submit_pending', 'de', $$Wird gesendet...$$, FALSE),

        ('app_account_page', 'messages_compose_help', 'en', $$This first multimedia pass accepts files up to 10 MB each across image, audio, PDF, DOCX, and PPTX formats.$$ , TRUE),
        ('app_account_page', 'messages_compose_help', 'es', $$Esta primera versión multimedia acepta archivos de hasta 10 MB cada uno en formatos de imagen, audio, PDF, DOCX y PPTX.$$ , FALSE),
        ('app_account_page', 'messages_compose_help', 'fr', $$Cette première version multimédia accepte des fichiers jusqu'à 10 Mo chacun aux formats image, audio, PDF, DOCX et PPTX.$$ , FALSE),
        ('app_account_page', 'messages_compose_help', 'de', $$Diese erste Multimedia-Version akzeptiert Dateien bis 10 MB pro Datei in den Formaten Bild, Audio, PDF, DOCX und PPTX.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_preparing_title', 'en', $$Preparing message...$$, TRUE),
        ('app_account_page', 'messages_compose_progress_preparing_title', 'es', $$Preparando mensaje...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_title', 'fr', $$Préparation du message...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_title', 'de', $$Nachricht wird vorbereitet...$$, FALSE),

        ('app_account_page', 'messages_compose_progress_preparing_body_with_files', 'en', $$We are packaging your note and selected files for secure upload.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_preparing_body_with_files', 'es', $$Estamos preparando tu nota y los archivos seleccionados para una carga segura.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_body_with_files', 'fr', $$Nous préparons votre note et les fichiers sélectionnés pour un téléversement sécurisé.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_body_with_files', 'de', $$Wir bereiten Ihre Notiz und die ausgewählten Dateien für einen sicheren Upload vor.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_preparing_body_no_files', 'en', $$We are preparing your message for delivery.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_preparing_body_no_files', 'es', $$Estamos preparando tu mensaje para enviarlo.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_body_no_files', 'fr', $$Nous préparons votre message pour l'envoi.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_preparing_body_no_files', 'de', $$Wir bereiten Ihre Nachricht für den Versand vor.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_uploading_title', 'en', $$Uploading files...$$, TRUE),
        ('app_account_page', 'messages_compose_progress_uploading_title', 'es', $$Subiendo archivos...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_title', 'fr', $$Téléversement des fichiers...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_title', 'de', $$Dateien werden hochgeladen...$$, FALSE),

        ('app_account_page', 'messages_compose_progress_uploading_body_with_files', 'en', $$Your selected files are being uploaded. Larger media can take a little longer.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_uploading_body_with_files', 'es', $$Tus archivos seleccionados se están subiendo. Los archivos grandes pueden tardar un poco más.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_body_with_files', 'fr', $$Vos fichiers sélectionnés sont en cours de téléversement. Les médias volumineux peuvent prendre un peu plus de temps.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_body_with_files', 'de', $$Ihre ausgewählten Dateien werden hochgeladen. Größere Medien können etwas länger dauern.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_uploading_body_no_files', 'en', $$Your message is on its way.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_uploading_body_no_files', 'es', $$Tu mensaje está en camino.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_body_no_files', 'fr', $$Votre message est en cours d'envoi.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_uploading_body_no_files', 'de', $$Ihre Nachricht ist unterwegs.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_processing_title', 'en', $$Processing message...$$, TRUE),
        ('app_account_page', 'messages_compose_progress_processing_title', 'es', $$Procesando mensaje...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_processing_title', 'fr', $$Traitement du message...$$, FALSE),
        ('app_account_page', 'messages_compose_progress_processing_title', 'de', $$Nachricht wird verarbeitet...$$, FALSE),

        ('app_account_page', 'messages_compose_progress_processing_body', 'en', $$DCX is storing the message and preparing the first analysis pass.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_processing_body', 'es', $$DCX está guardando el mensaje y preparando la primera pasada de análisis.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_processing_body', 'fr', $$DCX enregistre le message et prépare la première passe d'analyse.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_processing_body', 'de', $$DCX speichert die Nachricht und bereitet den ersten Analysedurchlauf vor.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_success_title', 'en', $$Message sent.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_success_title', 'es', $$Mensaje enviado.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_success_title', 'fr', $$Message envoyé.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_success_title', 'de', $$Nachricht gesendet.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_success_body', 'en', $$Your message is now in the inbox and ready for review in Messages.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_success_body', 'es', $$Tu mensaje ya está en la bandeja y listo para revisarse en Mensajes.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_success_body', 'fr', $$Votre message est maintenant dans la boîte de réception et prêt à être consulté dans Messages.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_success_body', 'de', $$Ihre Nachricht befindet sich jetzt im Posteingang und kann unter Nachrichten geprüft werden.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_error_title', 'en', $$We could not send that message.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_error_title', 'es', $$No pudimos enviar ese mensaje.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_error_title', 'fr', $$Nous n'avons pas pu envoyer ce message.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_error_title', 'de', $$Diese Nachricht konnte nicht gesendet werden.$$ , FALSE),

        ('app_account_page', 'messages_compose_progress_error_body', 'en', $$Please review the details below and retry when you are ready.$$ , TRUE),
        ('app_account_page', 'messages_compose_progress_error_body', 'es', $$Revisa los detalles a continuación y vuelve a intentarlo cuando quieras.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_error_body', 'fr', $$Veuillez vérifier les détails ci-dessous et réessayer lorsque vous serez prêt.$$ , FALSE),
        ('app_account_page', 'messages_compose_progress_error_body', 'de', $$Bitte prüfen Sie die folgenden Details und versuchen Sie es erneut, wenn Sie bereit sind.$$ , FALSE),

        ('app_account_page', 'messages_compose_error_retry_suggested_action', 'en', $$Retry after confirming the connection and selected files.$$ , TRUE),
        ('app_account_page', 'messages_compose_error_retry_suggested_action', 'es', $$Vuelve a intentarlo después de confirmar la conexión y los archivos seleccionados.$$ , FALSE),
        ('app_account_page', 'messages_compose_error_retry_suggested_action', 'fr', $$Réessayez après avoir confirmé la connexion et les fichiers sélectionnés.$$ , FALSE),
        ('app_account_page', 'messages_compose_error_retry_suggested_action', 'de', $$Versuchen Sie es erneut, nachdem Sie die Verbindung und die ausgewählten Dateien geprüft haben.$$ , FALSE),

        ('app_account_page', 'messages_compose_attachment_status_ready', 'en', $$Ready to send$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_ready', 'es', $$Listo para enviar$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_ready', 'fr', $$Prêt à envoyer$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_ready', 'de', $$Bereit zum Senden$$, FALSE),

        ('app_account_page', 'messages_compose_attachment_status_queued', 'en', $$Queued$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_queued', 'es', $$En cola$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_queued', 'fr', $$En file d'attente$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_queued', 'de', $$In Warteschlange$$, FALSE),

        ('app_account_page', 'messages_compose_attachment_status_uploading', 'en', $$Uploading$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_uploading', 'es', $$Subiendo$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_uploading', 'fr', $$Téléversement$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_uploading', 'de', $$Wird hochgeladen$$, FALSE),

        ('app_account_page', 'messages_compose_attachment_status_attached', 'en', $$Attached$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_attached', 'es', $$Adjuntado$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_attached', 'fr', $$Joint$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_attached', 'de', $$Angehängt$$, FALSE),

        ('app_account_page', 'messages_compose_attachment_status_sent', 'en', $$Sent$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_sent', 'es', $$Enviado$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_sent', 'fr', $$Envoyé$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_sent', 'de', $$Gesendet$$, FALSE),

        ('app_account_page', 'messages_compose_attachment_status_retry_needed', 'en', $$Retry needed$$, TRUE),
        ('app_account_page', 'messages_compose_attachment_status_retry_needed', 'es', $$Reintento necesario$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_retry_needed', 'fr', $$Nouvelle tentative nécessaire$$, FALSE),
        ('app_account_page', 'messages_compose_attachment_status_retry_needed', 'de', $$Erneuter Versuch nötig$$, FALSE),

        ('app_account_page', 'messages_table_column_channel', 'en', $$Channel$$, TRUE),
        ('app_account_page', 'messages_table_column_channel', 'es', $$Canal$$, FALSE),
        ('app_account_page', 'messages_table_column_channel', 'fr', $$Canal$$, FALSE),
        ('app_account_page', 'messages_table_column_channel', 'de', $$Kanal$$, FALSE),

        ('app_account_page', 'messages_table_column_format', 'en', $$Format$$, TRUE),
        ('app_account_page', 'messages_table_column_format', 'es', $$Formato$$, FALSE),
        ('app_account_page', 'messages_table_column_format', 'fr', $$Format$$, FALSE),
        ('app_account_page', 'messages_table_column_format', 'de', $$Format$$, FALSE),

        ('app_account_page', 'messages_table_column_status', 'en', $$Status$$, TRUE),
        ('app_account_page', 'messages_table_column_status', 'es', $$Estado$$, FALSE),
        ('app_account_page', 'messages_table_column_status', 'fr', $$Statut$$, FALSE),
        ('app_account_page', 'messages_table_column_status', 'de', $$Status$$, FALSE),

        ('app_account_page', 'messages_table_column_language', 'en', $$Language$$, TRUE),
        ('app_account_page', 'messages_table_column_language', 'es', $$Idioma$$, FALSE),
        ('app_account_page', 'messages_table_column_language', 'fr', $$Langue$$, FALSE),
        ('app_account_page', 'messages_table_column_language', 'de', $$Sprache$$, FALSE),

        ('app_account_page', 'messages_table_column_received', 'en', $$Received$$, TRUE),
        ('app_account_page', 'messages_table_column_received', 'es', $$Recibido$$, FALSE),
        ('app_account_page', 'messages_table_column_received', 'fr', $$Reçu$$, FALSE),
        ('app_account_page', 'messages_table_column_received', 'de', $$Empfangen$$, FALSE),

        ('app_account_page', 'messages_table_column_summary', 'en', $$Message$$, TRUE),
        ('app_account_page', 'messages_table_column_summary', 'es', $$Mensaje$$, FALSE),
        ('app_account_page', 'messages_table_column_summary', 'fr', $$Message$$, FALSE),
        ('app_account_page', 'messages_table_column_summary', 'de', $$Nachricht$$, FALSE),

        ('app_account_page', 'messages_detail_title', 'en', $$Message$$, TRUE),
        ('app_account_page', 'messages_detail_title', 'es', $$Mensaje$$, FALSE),
        ('app_account_page', 'messages_detail_title', 'fr', $$Message$$, FALSE),
        ('app_account_page', 'messages_detail_title', 'de', $$Nachricht$$, FALSE),

        ('app_account_page', 'messages_detail_empty', 'en', $$Choose a message to review it here.$$ , TRUE),
        ('app_account_page', 'messages_detail_empty', 'es', $$Elige un mensaje para revisarlo aquí.$$ , FALSE),
        ('app_account_page', 'messages_detail_empty', 'fr', $$Choisissez un message pour l'examiner ici.$$ , FALSE),
        ('app_account_page', 'messages_detail_empty', 'de', $$Wählen Sie eine Nachricht aus, um sie hier zu prüfen.$$ , FALSE),

        ('app_account_page', 'messages_detail_raw_text', 'en', $$Original$$, TRUE),
        ('app_account_page', 'messages_detail_raw_text', 'es', $$Original$$, FALSE),
        ('app_account_page', 'messages_detail_raw_text', 'fr', $$Original$$, FALSE),
        ('app_account_page', 'messages_detail_raw_text', 'de', $$Original$$, FALSE),

        ('app_account_page', 'messages_detail_derived_text', 'en', $$Synthesis$$, TRUE),
        ('app_account_page', 'messages_detail_derived_text', 'es', $$Síntesis$$, FALSE),
        ('app_account_page', 'messages_detail_derived_text', 'fr', $$Synthèse$$, FALSE),
        ('app_account_page', 'messages_detail_derived_text', 'de', $$Synthese$$, FALSE),

        ('app_account_page', 'messages_detail_summary', 'en', $$Summary$$, TRUE),
        ('app_account_page', 'messages_detail_summary', 'es', $$Resumen$$, FALSE),
        ('app_account_page', 'messages_detail_summary', 'fr', $$Résumé$$, FALSE),
        ('app_account_page', 'messages_detail_summary', 'de', $$Zusammenfassung$$, FALSE),

        ('app_account_page', 'messages_detail_description', 'en', $$Description$$, TRUE),
        ('app_account_page', 'messages_detail_description', 'es', $$Descripción$$, FALSE),
        ('app_account_page', 'messages_detail_description', 'fr', $$Description$$, FALSE),
        ('app_account_page', 'messages_detail_description', 'de', $$Beschreibung$$, FALSE),

        ('app_account_page', 'messages_detail_context', 'en', $$Context$$, TRUE),
        ('app_account_page', 'messages_detail_context', 'es', $$Contexto$$, FALSE),
        ('app_account_page', 'messages_detail_context', 'fr', $$Contexte$$, FALSE),
        ('app_account_page', 'messages_detail_context', 'de', $$Kontext$$, FALSE),

        ('app_account_page', 'messages_detail_transcription', 'en', $$Transcription$$, TRUE),
        ('app_account_page', 'messages_detail_transcription', 'es', $$Transcripción$$, FALSE),
        ('app_account_page', 'messages_detail_transcription', 'fr', $$Transcription$$, FALSE),
        ('app_account_page', 'messages_detail_transcription', 'de', $$Transkription$$, FALSE),

        ('app_account_page', 'messages_detail_language', 'en', $$Detected language$$, TRUE),
        ('app_account_page', 'messages_detail_language', 'es', $$Idioma detectado$$, FALSE),
        ('app_account_page', 'messages_detail_language', 'fr', $$Langue détectée$$, FALSE),
        ('app_account_page', 'messages_detail_language', 'de', $$Erkannte Sprache$$, FALSE),

        ('app_account_page', 'messages_detail_processing_status', 'en', $$Processing status$$, TRUE),
        ('app_account_page', 'messages_detail_processing_status', 'es', $$Estado del procesamiento$$, FALSE),
        ('app_account_page', 'messages_detail_processing_status', 'fr', $$Statut de traitement$$, FALSE),
        ('app_account_page', 'messages_detail_processing_status', 'de', $$Verarbeitungsstatus$$, FALSE),

        ('app_account_page', 'messages_detail_derivation_status', 'en', $$Derivation status$$, TRUE),
        ('app_account_page', 'messages_detail_derivation_status', 'es', $$Estado de derivación$$, FALSE),
        ('app_account_page', 'messages_detail_derivation_status', 'fr', $$Statut de dérivation$$, FALSE),
        ('app_account_page', 'messages_detail_derivation_status', 'de', $$Ableitungsstatus$$, FALSE),

        ('app_account_page', 'messages_detail_attachments', 'en', $$Attachments$$, TRUE),
        ('app_account_page', 'messages_detail_attachments', 'es', $$Adjuntos$$, FALSE),
        ('app_account_page', 'messages_detail_attachments', 'fr', $$Pièces jointes$$, FALSE),
        ('app_account_page', 'messages_detail_attachments', 'de', $$Anhänge$$, FALSE),

        ('app_account_page', 'messages_detail_attachments_empty', 'en', $$No files are attached to this message.$$ , TRUE),
        ('app_account_page', 'messages_detail_attachments_empty', 'es', $$No hay archivos adjuntos en este mensaje.$$ , FALSE),
        ('app_account_page', 'messages_detail_attachments_empty', 'fr', $$Aucun fichier n'est joint à ce message.$$ , FALSE),
        ('app_account_page', 'messages_detail_attachments_empty', 'de', $$Dieser Nachricht sind keine Dateien angehängt.$$ , FALSE),

        ('app_account_page', 'messages_status_received', 'en', $$Received$$, TRUE),
        ('app_account_page', 'messages_status_received', 'es', $$Recibido$$, FALSE),
        ('app_account_page', 'messages_status_received', 'fr', $$Reçu$$, FALSE),
        ('app_account_page', 'messages_status_received', 'de', $$Empfangen$$, FALSE),

        ('app_account_page', 'messages_status_queued', 'en', $$Queued$$, TRUE),
        ('app_account_page', 'messages_status_queued', 'es', $$En cola$$, FALSE),
        ('app_account_page', 'messages_status_queued', 'fr', $$En file d'attente$$, FALSE),
        ('app_account_page', 'messages_status_queued', 'de', $$In Warteschlange$$, FALSE),

        ('app_account_page', 'messages_status_processing', 'en', $$Processing$$, TRUE),
        ('app_account_page', 'messages_status_processing', 'es', $$Procesando$$, FALSE),
        ('app_account_page', 'messages_status_processing', 'fr', $$Traitement en cours$$, FALSE),
        ('app_account_page', 'messages_status_processing', 'de', $$Wird verarbeitet$$, FALSE),

        ('app_account_page', 'messages_status_ready', 'en', $$Ready$$, TRUE),
        ('app_account_page', 'messages_status_ready', 'es', $$Listo$$, FALSE),
        ('app_account_page', 'messages_status_ready', 'fr', $$Prêt$$, FALSE),
        ('app_account_page', 'messages_status_ready', 'de', $$Bereit$$, FALSE),

        ('app_account_page', 'messages_status_analysing', 'en', $$Analysing$$, TRUE),
        ('app_account_page', 'messages_status_analysing', 'es', $$Analizando$$, FALSE),
        ('app_account_page', 'messages_status_analysing', 'fr', $$Analyse en cours$$, FALSE),
        ('app_account_page', 'messages_status_analysing', 'de', $$Wird analysiert$$, FALSE),

        ('app_account_page', 'messages_status_failed', 'en', $$Failed$$, TRUE),
        ('app_account_page', 'messages_status_failed', 'es', $$Fallido$$, FALSE),
        ('app_account_page', 'messages_status_failed', 'fr', $$Échec$$, FALSE),
        ('app_account_page', 'messages_status_failed', 'de', $$Fehlgeschlagen$$, FALSE),

        ('app_account_page', 'messages_derivation_not_required', 'en', $$Not required$$, TRUE),
        ('app_account_page', 'messages_derivation_not_required', 'es', $$No requerido$$, FALSE),
        ('app_account_page', 'messages_derivation_not_required', 'fr', $$Non requis$$, FALSE),
        ('app_account_page', 'messages_derivation_not_required', 'de', $$Nicht erforderlich$$, FALSE),

        ('app_account_page', 'messages_derivation_pending', 'en', $$Pending$$, TRUE),
        ('app_account_page', 'messages_derivation_pending', 'es', $$Pendiente$$, FALSE),
        ('app_account_page', 'messages_derivation_pending', 'fr', $$En attente$$, FALSE),
        ('app_account_page', 'messages_derivation_pending', 'de', $$Ausstehend$$, FALSE),

        ('app_account_page', 'messages_derivation_completed', 'en', $$Completed$$, TRUE),
        ('app_account_page', 'messages_derivation_completed', 'es', $$Completado$$, FALSE),
        ('app_account_page', 'messages_derivation_completed', 'fr', $$Terminé$$, FALSE),
        ('app_account_page', 'messages_derivation_completed', 'de', $$Abgeschlossen$$, FALSE),

        ('app_account_page', 'messages_derivation_failed', 'en', $$Failed$$, TRUE),
        ('app_account_page', 'messages_derivation_failed', 'es', $$Fallido$$, FALSE),
        ('app_account_page', 'messages_derivation_failed', 'fr', $$Échec$$, FALSE),
        ('app_account_page', 'messages_derivation_failed', 'de', $$Fehlgeschlagen$$, FALSE),

        ('app_account_page', 'messages_toggle_show', 'en', $$Show$$, TRUE),
        ('app_account_page', 'messages_toggle_show', 'es', $$Mostrar$$, FALSE),
        ('app_account_page', 'messages_toggle_show', 'fr', $$Afficher$$, FALSE),
        ('app_account_page', 'messages_toggle_show', 'de', $$Anzeigen$$, FALSE),

        ('app_account_page', 'messages_toggle_hide', 'en', $$Hide$$, TRUE),
        ('app_account_page', 'messages_toggle_hide', 'es', $$Ocultar$$, FALSE),
        ('app_account_page', 'messages_toggle_hide', 'fr', $$Masquer$$, FALSE),
        ('app_account_page', 'messages_toggle_hide', 'de', $$Ausblenden$$, FALSE),

        ('app_account_page', 'messages_download_label', 'en', $$Download$$, TRUE),
        ('app_account_page', 'messages_download_label', 'es', $$Descargar$$, FALSE),
        ('app_account_page', 'messages_download_label', 'fr', $$Télécharger$$, FALSE),
        ('app_account_page', 'messages_download_label', 'de', $$Herunterladen$$, FALSE),

        ('app_account_page', 'messages_format_label_text', 'en', $$text$$, TRUE),
        ('app_account_page', 'messages_format_label_text', 'es', $$texto$$, FALSE),
        ('app_account_page', 'messages_format_label_text', 'fr', $$texte$$, FALSE),
        ('app_account_page', 'messages_format_label_text', 'de', $$text$$, FALSE),

        ('app_account_page', 'messages_format_label_image', 'en', $$image$$, TRUE),
        ('app_account_page', 'messages_format_label_image', 'es', $$imagen$$, FALSE),
        ('app_account_page', 'messages_format_label_image', 'fr', $$image$$, FALSE),
        ('app_account_page', 'messages_format_label_image', 'de', $$bild$$, FALSE),

        ('app_account_page', 'messages_format_label_audio', 'en', $$audio$$, TRUE),
        ('app_account_page', 'messages_format_label_audio', 'es', $$audio$$, FALSE),
        ('app_account_page', 'messages_format_label_audio', 'fr', $$audio$$, FALSE),
        ('app_account_page', 'messages_format_label_audio', 'de', $$audio$$, FALSE),

        ('app_account_page', 'messages_format_label_document', 'en', $$doc$$, TRUE),
        ('app_account_page', 'messages_format_label_document', 'es', $$doc$$, FALSE),
        ('app_account_page', 'messages_format_label_document', 'fr', $$doc$$, FALSE),
        ('app_account_page', 'messages_format_label_document', 'de', $$dok$$, FALSE),

        ('app_account_page', 'messages_format_label_mixed', 'en', $$mixed$$, TRUE),
        ('app_account_page', 'messages_format_label_mixed', 'es', $$mixto$$, FALSE),
        ('app_account_page', 'messages_format_label_mixed', 'fr', $$mixte$$, FALSE),
        ('app_account_page', 'messages_format_label_mixed', 'de', $$gemischt$$, FALSE),

        ('app_account_page', 'messages_title_fallback_message', 'en', $$Message$$, TRUE),
        ('app_account_page', 'messages_title_fallback_message', 'es', $$Mensaje$$, FALSE),
        ('app_account_page', 'messages_title_fallback_message', 'fr', $$Message$$, FALSE),
        ('app_account_page', 'messages_title_fallback_message', 'de', $$Nachricht$$, FALSE),

        ('app_account_page', 'messages_title_fallback_image', 'en', $$Image$$, TRUE),
        ('app_account_page', 'messages_title_fallback_image', 'es', $$Imagen$$, FALSE),
        ('app_account_page', 'messages_title_fallback_image', 'fr', $$Image$$, FALSE),
        ('app_account_page', 'messages_title_fallback_image', 'de', $$Bild$$, FALSE),

        ('app_account_page', 'messages_title_fallback_audio', 'en', $$Audio message$$, TRUE),
        ('app_account_page', 'messages_title_fallback_audio', 'es', $$Mensaje de audio$$, FALSE),
        ('app_account_page', 'messages_title_fallback_audio', 'fr', $$Message audio$$, FALSE),
        ('app_account_page', 'messages_title_fallback_audio', 'de', $$Audionachricht$$, FALSE),

        ('app_account_page', 'messages_title_fallback_document', 'en', $$Document$$, TRUE),
        ('app_account_page', 'messages_title_fallback_document', 'es', $$Documento$$, FALSE),
        ('app_account_page', 'messages_title_fallback_document', 'fr', $$Document$$, FALSE),
        ('app_account_page', 'messages_title_fallback_document', 'de', $$Dokument$$, FALSE),

        ('app_account_page', 'messages_title_fallback_attachment', 'en', $$Attachment$$, TRUE),
        ('app_account_page', 'messages_title_fallback_attachment', 'es', $$Adjunto$$, FALSE),
        ('app_account_page', 'messages_title_fallback_attachment', 'fr', $$Pièce jointe$$, FALSE),
        ('app_account_page', 'messages_title_fallback_attachment', 'de', $$Anhang$$, FALSE)
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
),
updated_live_rows AS (
    UPDATE stephen_dcx_ux_strings existing
    SET text = desired_strings.text_value
    FROM desired_strings
    JOIN language_rows target_language
      ON target_language.language_code = desired_strings.language_code
    WHERE existing.string_group = desired_strings.string_group
      AND existing.string_key = desired_strings.string_key
      AND existing.language_id = target_language.id
      AND existing.is_live = TRUE
      AND existing.text <> desired_strings.text_value
    RETURNING existing.id
),
inserted_english_originals AS (
    INSERT INTO stephen_dcx_ux_strings
    (string_group, string_key, language_id, text, is_original, is_live, version_of_id, translation_of_id)
    SELECT
        desired_strings.string_group,
        desired_strings.string_key,
        english_language.id,
        desired_strings.text_value,
        TRUE,
        TRUE,
        NULL,
        NULL
    FROM desired_strings
    JOIN language_rows english_language
      ON english_language.language_code = desired_strings.language_code
    WHERE desired_strings.language_code = 'en'
      AND desired_strings.is_original = TRUE
      AND NOT EXISTS (
          SELECT 1
          FROM stephen_dcx_ux_strings existing
          WHERE existing.string_group = desired_strings.string_group
            AND existing.string_key = desired_strings.string_key
            AND existing.language_id = english_language.id
            AND existing.is_original = TRUE
            AND existing.is_live = TRUE
      )
    RETURNING id, string_group, string_key
),
english_live_originals_after_seed AS (
    SELECT id, string_group, string_key
    FROM english_live_originals
    UNION ALL
    SELECT id, string_group, string_key
    FROM inserted_english_originals
)
INSERT INTO stephen_dcx_ux_strings
(string_group, string_key, language_id, text, is_original, is_live, version_of_id, translation_of_id)
SELECT
    desired_strings.string_group,
    desired_strings.string_key,
    target_language.id,
    desired_strings.text_value,
    FALSE,
    TRUE,
    NULL,
    english_live_originals_after_seed.id
FROM desired_strings
JOIN language_rows target_language
  ON target_language.language_code = desired_strings.language_code
JOIN english_live_originals_after_seed
  ON english_live_originals_after_seed.string_group = desired_strings.string_group
 AND english_live_originals_after_seed.string_key = desired_strings.string_key
WHERE desired_strings.language_code <> 'en'
  AND NOT EXISTS (
      SELECT 1
      FROM stephen_dcx_ux_strings existing
      WHERE existing.string_group = desired_strings.string_group
        AND existing.string_key = desired_strings.string_key
        AND existing.language_id = target_language.id
        AND existing.is_live = TRUE
  );
