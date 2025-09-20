// Osmium-main/ai_assistant/ai_assistant/page/ai_assistant/ai_assistant.js
// FINAL CORRECTED VERSION

frappe.pages['ai_assistant'].on_page_load = function(wrapper) {
    new AIAssistantPage(wrapper);
};

class AIAssistantPage {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.page = frappe.ui.make_app_page({
            parent: this.wrapper,
            title: __('AI Assistant'),
            single_column: true
        });

        this.state = {
            current_session_id: null,
            user: {},
            settings: {},
            permissions: {},
            is_sending: false,
            pending_command: null
        };
        
        this.setup_page();
    }

    setup_page() {
        // --- FIX: Render the HTML content passed from the Python context ---
        $(this.page.body).html(frappe.boot.page.html_content);
        // --- END FIX ---
        
        this.setup_elements();
        this.setup_event_handlers();
        this.setup_auto_resize();
        this.load_initial_data();
    }

    setup_elements() {
        // Cache frequently used elements from the rendered template
        this.$chat_messages = this.page.body.find('#chat-messages');
        this.$chat_input = this.page.body.find('#chat-input');
        this.$send_button = this.page.body.find('#send-button');
        this.$session_list = this.page.body.find('#session-list');
        this.$typing_indicator = this.page.body.find('#typing-indicator');
        this.$char_count = this.page.body.find('#char-count');
        this.$welcome_message = this.page.body.find('.welcome-message');
    }

    setup_event_handlers() {
        // Chat input handlers
        this.$chat_input.on('input', () => this.handle_input_change());
        this.$chat_input.on('keydown', (e) => this.handle_keydown(e));

        // Button handlers (within the rendered page body)
        this.page.body.find('#send-button').on('click', () => this.send_message());
        this.page.body.find('#new-session').on('click', () => this.start_new_session());
        this.page.body.find('#clear-history').on('click', () => this.confirm_clear_history());
        this.page.body.find('#toggle-settings').on('click', () => this.show_settings_modal());
        
        // Settings modal handlers
        this.page.body.find('#save-settings').on('click', () => this.save_settings());
        this.page.body.find('#provider').on('change', (e) => this.toggle_provider_sections(e.target.value));

        // Command confirmation handlers
        this.page.body.find('#confirm-command').on('click', () => this.execute_confirmed_command());

        // Quick action handlers
        this.page.body.find('.quick-action').on('click', (e) => {
            const query = $(e.currentTarget).data('query');
            this.$chat_input.val(query);
            this.handle_input_change();
            this.send_message();
        });

        // Session list handlers
        this.$session_list.on('click', '.session-item', (e) => {
            const sessionId = $(e.currentTarget).data('session-id');
            this.load_session(sessionId);
        });
    }
    
    setup_auto_resize() {
        this.$chat_input.on('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

    load_initial_data() {
        frappe.call({
            method: 'ai_assistant.ai_assistant.page.ai_assistant.ai_assistant.get_page_data',
        }).then((r) => {
            if (r.message && r.message.success) {
                this.state.user = r.message.user;
                this.state.settings = r.message.settings;
                this.state.permissions = r.message.permissions;
                this.update_ui();
                this.load_recent_sessions();
                this.check_ai_status();
            } else {
                frappe.msgprint(__('Failed to load page data'));
            }
        }).fail(() => {
            frappe.msgprint(__('Error loading AI Assistant'));
        });
    }

    update_ui() {
        const currentModel = this.state.settings.provider === 'openai'
            ? this.state.settings.openai_model || 'gpt-5'
            : this.state.settings.ollama_model || 'llama2';
        this.page.body.find('#current-model').text(currentModel);

        this.page.body.find('#safe-mode-status').html(
            this.state.settings.safe_mode ?
            '<i class="indicator green"></i> Enabled' :
            '<i class="indicator red"></i> Disabled'
        );

        if (!this.state.permissions.can_manage_settings) {
            this.page.body.find('#toggle-settings').hide();
        }

        if (!this.state.permissions.can_send_messages) {
            this.$chat_input.prop('disabled', true);
            this.$send_button.prop('disabled', true);
        }
    }

    handle_input_change() {
        const text = this.$chat_input.val().trim();
        const charCount = text.length;
        this.$char_count.text(`${charCount}/2000`);
        this.$send_button.prop('disabled', !text || charCount > 2000 || this.state.is_sending);
    }
    
    handle_keydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!this.$send_button.prop('disabled')) {
                this.send_message();
            }
        }
    }

    send_message() {
        const message = this.$chat_input.val().trim();
        if (!message || this.state.is_sending) return;

        this.state.is_sending = true;
        this.toggle_ui_lock(true);
        this.add_message('user', message);
        this.$chat_input.val('').trigger('input');

        frappe.call({
            method: 'ai_assistant.ai_assistant.api.send_message',
            args: {
                session_id: this.state.current_session_id,
                message: message,
                role: 'user'
            }
        }).then((r) => {
            if (r.message && r.message.success) {
                this.state.current_session_id = r.message.session_id;
                this.add_message('assistant', r.message.ai_response);
                if (r.message.command_analysis && r.message.command_analysis.command) {
                    this.handle_command_analysis(r.message.command_analysis, r.message.assistant_message_id);
                }
                this.update_session_title_from_api(this.state.current_session_id);
            } else {
                this.add_message('assistant', r.message?.error || __('Sorry, I encountered an error.'), true);
            }
        }).fail(() => {
            this.add_message('assistant', __('Connection error. Please try again.'), true);
        }).always(() => {
            this.state.is_sending = false;
            this.toggle_ui_lock(false);
        });
    }
    
    add_message(role, content, is_error = false) {
        this.$welcome_message.hide();
        const user_avatar_src = this.state.user.image || frappe.avatar(this.state.user.name);
        const avatar = role === 'user' ?
            `<img src="${user_avatar_src}" class="user-avatar-image" alt="${this.state.user.name}">` :
            '<div class="assistant-avatar"><i class="fa fa-robot"></i></div>';
        
        const messageHtml = `
            <div class="message ${role}-message ${is_error ? 'error-message' : ''}">
                ${avatar}
                <div class="message-content">
                    <div class="message-text">${frappe.markdown(content || "")}</div>
                    <div class="message-time">${frappe.datetime.now_time()}</div>
                </div>
            </div>`;
        this.$chat_messages.append(messageHtml);
        this.scroll_to_bottom();
    }
    
    toggle_ui_lock(is_locked) {
        this.$chat_input.prop('disabled', is_locked);
        this.$send_button.prop('disabled', is_locked);
        this.$typing_indicator.toggle(is_locked);
        if (is_locked) {
            this.scroll_to_bottom();
        }
    }
    
    scroll_to_bottom() {
        this.$chat_messages.scrollTop(this.$chat_messages[0].scrollHeight);
    }
    
    start_new_session() {
        this.state.current_session_id = null;
        this.$chat_messages.find('.message').remove();
        this.$welcome_message.show();
        this.page.body.find('#current-session-title').text(__('New Chat Session'));
        this.load_recent_sessions(); 
        frappe.show_alert({ message: __('New chat session started.'), indicator: 'green' });
    }

    confirm_clear_history() {
        frappe.confirm(
            __('Are you sure you want to clear the current chat history?'),
            () => this.clear_history()
        );
    }

    clear_history() {
        if (!this.state.current_session_id) {
            this.start_new_session();
            return;
        }
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.clear_history',
            args: { session_id: this.state.current_session_id }
        }).then(() => {
            this.start_new_session();
            frappe.show_alert({message: __('History cleared'), indicator: 'green'});
        });
    }

    load_recent_sessions() {
        frappe.call('ai_assistant.ai_assistant.api.get_chat_sessions').then(r => {
            if (r.message && r.message.success) {
                this.render_session_list(r.message.sessions);
            }
        });
    }
    
    render_session_list(sessions) {
        if (!sessions || sessions.length === 0) {
            this.$session_list.html('<div class="no-sessions text-muted text-center"><p>' + __('No recent sessions') + '</p></div>');
            return;
        }
        const html = sessions.map(session => {
            const isActive = session.name === this.state.current_session_id ? 'active' : '';
            return `
                <div class="session-item ${isActive}" data-session-id="${session.name}">
                    <div class="session-title">${session.title}</div>
                    <div class.session-meta">
                        <small class="text-muted">${frappe.datetime.comment_when(session.session_start)}</small>
                        <span class="indicator ${session.status === 'Active' ? 'green' : 'grey'}"></span>
                    </div>
                </div>`;
        }).join('');
        this.$session_list.html(html);
    }

    load_session(session_id) {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.get_chat_messages',
            args: { session_id: session_id }
        }).then(r => {
            if (r.message && r.message.success) {
                this.state.current_session_id = session_id;
                this.render_chat_messages(r.message.messages);
                this.update_session_title_from_list(session_id);
            }
        });
    }

    render_chat_messages(messages) {
        this.$chat_messages.find('.message').remove();
        if (!messages || messages.length === 0) {
            this.$welcome_message.show();
        } else {
            this.$welcome_message.hide();
            messages.forEach(msg => {
                this.add_message(msg.role, msg.content, msg.is_error);
            });
        }
    }
    
    update_session_title_from_api(session_id) {
        frappe.db.get_value("AI Chat Session", session_id, "title").then(r => {
            if (r.message.title) {
                this.page.body.find('#current-session-title').text(r.message.title);
                this.load_recent_sessions();
            }
        });
    }

    update_session_title_from_list(session_id) {
        const sessionItem = this.$session_list.find(`.session-item[data-session-id="${session_id}"]`);
        if (sessionItem.length) {
            const title = sessionItem.find('.session-title').text();
            this.page.body.find('#current-session-title').text(title);
            this.$session_list.find('.session-item').removeClass('active');
            sessionItem.addClass('active');
        }
    }

    check_ai_status() {
        this.page.body.find('#ai-status .status-value').html(`<i class="indicator green"></i> ${this.state.settings.provider}`);
    }
    
    // Using Frappe's Dialog for modals is more robust
    show_settings_modal() {
        const d = new frappe.ui.Dialog({
            title: __('AI Assistant Settings'),
            fields: [
                {
                    label: 'AI Provider',
                    fieldname: 'provider',
                    fieldtype: 'Select',
                    options: 'ollama\nopenai',
                    default: this.state.settings.provider,
                },
                {
                    label: 'Ollama Server URL',
                    fieldname: 'ollama_url',
                    fieldtype: 'Data',
                    default: this.state.settings.ollama_url,
                    depends_on: 'eval:doc.provider=="ollama"'
                },
                // Add all other fields from your HTML modal here
            ],
            primary_action_label: __('Save Settings'),
            primary_action: (values) => {
                this.save_settings(values);
                d.hide();
            }
        });
        d.show();
    }
    
    save_settings(settings_values) {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.update_settings',
            args: settings_values
        }).then(r => {
            if (r.message) {
                this.state.settings = r.message;
                this.update_ui();
                frappe.show_alert({message: __('Settings saved'), indicator: 'green'});
            }
        });
    }
}
