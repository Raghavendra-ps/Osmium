// Copyright (c) 2025, ERPNext and contributors
// For license information, please see license.txt

frappe.pages['ai_assistant'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('AI Assistant'),
        single_column: true
    });

    // Initialize the AI Assistant interface
    new AIAssistantInterface(page);
};

class AIAssistantInterface {
    constructor(page) {
        this.page = page;
        this.wrapper = page.wrapper;
        this.current_session_id = null;
        this.user_data = null;
        this.settings = {};
        this.permissions = {};
        this.pending_command = null;
        
        this.setup_page();
        this.init_realtime();
        this.load_initial_data();
    }

    setup_page() {
        // Set up the main page layout
        $(this.wrapper).find('.layout-main-section').html(frappe.render_template('ai_assistant', {}));
        
        this.setup_elements();
        this.setup_event_handlers();
        this.setup_auto_resize();
    }

    setup_elements() {
        // Cache frequently used elements
        this.$chat_messages = $('#chat-messages');
        this.$chat_input = $('#chat-input');
        this.$send_button = $('#send-button');
        this.$session_list = $('#session-list');
        this.$typing_indicator = $('#typing-indicator');
        this.$char_count = $('#char-count');
    }

    setup_event_handlers() {
        const self = this;

        // Chat input handlers
        this.$chat_input.on('input', () => this.handle_input_change());
        this.$chat_input.on('keydown', (e) => this.handle_keydown(e));

        // Button handlers
        this.$send_button.on('click', () => this.send_message());
        $('#new-session').on('click', () => this.create_new_session());
        $('#clear-history').on('click', () => this.confirm_clear_history());
        $('#toggle-settings').on('click', () => this.show_settings_modal());

        // Settings modal handlers
        $('#save-settings').on('click', () => this.save_settings());
        $('#provider').on('change', (e) => this.toggle_provider_sections(e.target.value));

        // Command confirmation handlers
        $('#confirm-command').on('click', () => this.execute_confirmed_command());

        // Quick action handlers
        $('.quick-action').on('click', function() {
            const query = $(this).data('query');
            self.$chat_input.val(query);
            self.handle_input_change();
            self.send_message();
        });

        // Session list handlers
        this.$session_list.on('click', '.session-item', function() {
            const sessionId = $(this).data('session-id');
            self.load_session(sessionId);
        });
    }

    setup_auto_resize() {
        // Auto-resize textarea
        this.$chat_input.on('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

    init_realtime() {
        // Set up realtime updates for chat messages
        if (frappe.realtime) {
            frappe.realtime.on('ai_assistant_message', (data) => {
                if (data.session_id === this.current_session_id) {
                    this.handle_realtime_message(data);
                }
            });

            frappe.realtime.on('ai_assistant_status', (data) => {
                this.update_status_panel(data);
            });
        }
    }

    load_initial_data() {
        frappe.call({
            method: 'ai_assistant.ai_assistant.page.ai_assistant.ai_assistant.get_page_data',
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.user_data = r.message.user;
                    this.settings = r.message.settings;
                    this.permissions = r.message.permissions;
                    this.update_ui();
                    this.load_recent_sessions();
                    this.check_ai_status();
                } else {
                    frappe.msgprint(__('Failed to load page data'));
                }
            },
            error: () => {
                frappe.msgprint(__('Error loading AI Assistant'));
            }
        });
    }

    update_ui() {
        // Update status panel with current model based on provider
        const currentModel = this.settings.provider === 'openai' 
            ? this.settings.openai_model || 'gpt-5'
            : this.settings.ollama_model || 'llama2';
        $('#current-model').text(currentModel);
        
        $('#safe-mode-status').html(
            this.settings.safe_mode ? 
            '<i class="indicator green"></i> Enabled' : 
            '<i class="indicator red"></i> Disabled'
        );

        // Hide settings button if no permission
        if (!this.permissions.can_manage_settings) {
            $('#toggle-settings').hide();
        }

        // Disable input if no permission to send messages
        if (!this.permissions.can_send_messages) {
            this.$chat_input.prop('disabled', true);
            this.$send_button.prop('disabled', true);
        }
    }

    handle_input_change() {
        const text = this.$chat_input.val().trim();
        const charCount = text.length;
        
        this.$char_count.text(`${charCount}/2000`);
        this.$send_button.prop('disabled', !text || charCount > 2000);
        
        if (charCount > 1900) {
            this.$char_count.addClass('text-warning');
        } else if (charCount > 2000) {
            this.$char_count.addClass('text-danger');
        } else {
            this.$char_count.removeClass('text-warning text-danger');
        }
    }

    handle_keydown(e) {
        if (e.key === 'Enter') {
            if (e.shiftKey) {
                // Allow new line with Shift+Enter
                return true;
            } else {
                // Send message with Enter
                e.preventDefault();
                if (!this.$send_button.prop('disabled')) {
                    this.send_message();
                }
            }
        }
    }

    send_message() {
        const message = this.$chat_input.val().trim();
        if (!message) return;

        // Clear input and disable button
        this.$chat_input.val('').trigger('input');
        this.handle_input_change();

        // Add user message to chat
        this.add_message('user', message);

        // Show typing indicator
        this.show_typing_indicator();

        // Send to backend
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.send_message',
            args: {
                session_id: this.current_session_id,
                message: message,
                role: 'user'
            },
            callback: (r) => {
                this.hide_typing_indicator();
                
                if (r.message && r.message.success) {
                    this.current_session_id = r.message.session_id;
                    
                    // Add AI response
                    this.add_message('assistant', r.message.ai_response);

                    // Handle command analysis
                    if (r.message.command_analysis && r.message.command_analysis.command) {
                        this.handle_command_analysis(r.message.command_analysis, r.message.assistant_message_id);
                    }

                    // Update session title if needed
                    this.update_session_title();
                } else {
                    this.add_message('assistant', r.message?.error || __('Sorry, I encountered an error processing your request.'), true);
                }
            },
            error: () => {
                this.hide_typing_indicator();
                this.add_message('assistant', __('Connection error. Please try again.'), true);
            }
        });
    }

    add_message(role, content, is_error = false) {
        const messageClass = role === 'user' ? 'user-message' : 'assistant-message';
        const errorClass = is_error ? 'error-message' : '';
        
        const avatar = role === 'user' ? 
            `<img src="${this.user_data?.image || '/assets/frappe/images/default-avatar.png'}" class="user-avatar">` :
            '<div class="assistant-avatar"><i class="fa fa-robot"></i></div>';

        const messageHtml = `
            <div class="message ${messageClass} ${errorClass}">
                ${avatar}
                <div class="message-content">
                    <div class="message-text">${this.format_message_content(content)}</div>
                    <div class="message-time">${moment().format('HH:mm')}</div>
                </div>
            </div>
        `;

        this.$chat_messages.append(messageHtml);
        this.scroll_to_bottom();
    }

    format_message_content(content) {
        // Basic formatting for message content
        return content
            .replace(/\n/g, '<br>')
            .replace(/```(\w+)?\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    show_typing_indicator() {
        this.$typing_indicator.show();
        this.scroll_to_bottom();
    }

    hide_typing_indicator() {
        this.$typing_indicator.hide();
    }

    scroll_to_bottom() {
        const chatContainer = this.$chat_messages[0];
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    handle_command_analysis(analysis, message_id) {
        if (analysis.isDestructive && this.settings.confirm_destructive) {
            // Show confirmation modal for destructive commands
            this.pending_command = {
                command: analysis.command,
                description: analysis.description,
                message_id: message_id
            };
            this.show_command_confirmation_modal(analysis);
        } else if (analysis.command && analysis.category !== 'other') {
            // Auto-execute non-destructive commands
            this.execute_command(analysis.command, message_id);
        }
    }

    show_command_confirmation_modal(analysis) {
        $('#command-preview').text(analysis.command);
        $('#command-description').text(analysis.description);
        $('#command-modal').modal('show');
    }

    execute_confirmed_command() {
        if (this.pending_command) {
            $('#command-modal').modal('hide');
            this.execute_command(this.pending_command.command, this.pending_command.message_id);
            this.pending_command = null;
        }
    }

    execute_command(command, message_id) {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.confirm_execute',
            args: {
                message_id: message_id,
                command: command
            },
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.add_message('assistant', 
                        `Command executed successfully:\n\`\`\`\n${JSON.stringify(r.message.result, null, 2)}\n\`\`\``);
                } else {
                    this.add_message('assistant', 
                        `Command execution failed: ${r.message?.error || 'Unknown error'}`, true);
                }
            }
        });
    }

    create_new_session() {
        frappe.call({
            method: 'ai_assistant.ai_assistant.page.ai_assistant.ai_assistant.initialize_session',
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.current_session_id = r.message.session.id;
                    this.$chat_messages.find('.message').remove();
                    this.show_welcome_message();
                    this.load_recent_sessions();
                    frappe.show_alert({message: __('New session created'), indicator: 'green'});
                } else {
                    frappe.msgprint(__('Failed to create new session'));
                }
            }
        });
    }

    show_welcome_message() {
        // The welcome message is already in the HTML template
        $('.welcome-message').show();
    }

    confirm_clear_history() {
        frappe.confirm(
            __('Are you sure you want to clear all chat history? This action cannot be undone.'),
            () => {
                this.clear_history();
            }
        );
    }

    clear_history() {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.clear_history',
            args: {
                session_id: this.current_session_id
            },
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.$chat_messages.find('.message').remove();
                    this.show_welcome_message();
                    this.current_session_id = null;
                    this.load_recent_sessions();
                    frappe.show_alert({message: __('History cleared'), indicator: 'green'});
                } else {
                    frappe.msgprint(__('Failed to clear history'));
                }
            }
        });
    }

    show_settings_modal() {
        // Populate current settings
        $('#provider').val(this.settings.provider || 'ollama');
        $('#ollama-url').val(this.settings.ollama_url);
        $('#ollama-model').val(this.settings.ollama_model);
        // Don't populate API key for security - leave blank for new input
        $('#openai-api-key').val('');
        if (this.settings.has_openai_key) {
            $('#openai-api-key').attr('placeholder', 'API key is configured (enter new key to change)');
        }
        $('#openai-model').val(this.settings.openai_model);
        $('#safe-mode').prop('checked', this.settings.safe_mode);
        $('#confirm-destructive').prop('checked', this.settings.confirm_destructive);
        $('#log-commands').prop('checked', this.settings.log_commands);
        
        // Show/hide relevant sections based on provider
        this.toggle_provider_sections(this.settings.provider || 'ollama');
        
        $('#settings-modal').modal('show');
    }

    save_settings() {
        const settings = {
            provider: $('#provider').val(),
            ollama_url: $('#ollama-url').val(),
            ollama_model: $('#ollama-model').val(),
            openai_model: $('#openai-model').val(),
            safe_mode: $('#safe-mode').prop('checked'),
            confirm_destructive: $('#confirm-destructive').prop('checked'),
            log_commands: $('#log-commands').prop('checked')
        };
        
        // Only include API key if it's not empty (to avoid overwriting with blank)
        const apiKey = $('#openai-api-key').val().trim();
        if (apiKey) {
            settings.openai_api_key = apiKey;
        }

        frappe.call({
            method: 'ai_assistant.ai_assistant.api.update_settings',
            args: settings,
            callback: (r) => {
                if (r.message) {
                    this.settings = r.message;
                    this.update_ui();
                    $('#settings-modal').modal('hide');
                    frappe.show_alert({message: __('Settings saved'), indicator: 'green'});
                    this.check_ai_status();
                } else {
                    frappe.msgprint(__('Failed to save settings'));
                }
            }
        });
    }

    toggle_provider_sections(provider) {
        if (provider === 'openai') {
            $('.ollama-section').hide();
            $('.openai-section').show();
        } else {
            $('.ollama-section').show();
            $('.openai-section').hide();
        }
    }

    load_recent_sessions() {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.get_chat_sessions',
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.render_session_list(r.message.sessions);
                }
            }
        });
    }

    render_session_list(sessions) {
        if (!sessions || sessions.length === 0) {
            this.$session_list.html('<div class="no-sessions text-muted text-center"><p>' + __('No recent sessions') + '</p></div>');
            return;
        }

        let html = '';
        sessions.forEach(session => {
            const isActive = session.name === this.current_session_id ? 'active' : '';
            const statusIcon = session.status === 'Active' ? 'green' : 'grey';
            
            html += `
                <div class="session-item ${isActive}" data-session-id="${session.name}">
                    <div class="session-title">${session.title}</div>
                    <div class="session-meta">
                        <small class="text-muted">${moment(session.session_start).fromNow()}</small>
                        <span class="indicator ${statusIcon}"></span>
                    </div>
                </div>
            `;
        });

        this.$session_list.html(html);
    }

    load_session(session_id) {
        frappe.call({
            method: 'ai_assistant.ai_assistant.api.get_chat_messages',
            args: {
                session_id: session_id
            },
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.current_session_id = session_id;
                    this.render_chat_messages(r.message.messages);
                    this.update_session_title();
                } else {
                    frappe.msgprint(__('Failed to load session'));
                }
            }
        });
    }

    render_chat_messages(messages) {
        this.$chat_messages.find('.message').remove();
        
        if (!messages || messages.length === 0) {
            this.show_welcome_message();
            return;
        }

        messages.forEach(message => {
            this.add_message(message.role, message.content, message.is_error);
        });
    }

    update_session_title() {
        if (this.current_session_id) {
            const sessionItem = $(`.session-item[data-session-id="${this.current_session_id}"]`);
            if (sessionItem.length) {
                const title = sessionItem.find('.session-title').text();
                $('#current-session-title').text(title);
                $('.session-item').removeClass('active');
                sessionItem.addClass('active');
            }
        }
    }

    check_ai_status() {
        // Simple status check - in a real implementation, you might have a dedicated endpoint
        $('#ai-status').html('<i class="indicator orange"></i> ' + __('Checking...'));
        
        // Simulate status check
        setTimeout(() => {
            $('#ai-status').html('<i class="indicator green"></i> ' + __('Connected'));
        }, 1000);
    }

    handle_realtime_message(data) {
        // Handle real-time message updates
        if (data.type === 'message') {
            this.add_message(data.role, data.content);
        } else if (data.type === 'typing') {
            if (data.typing) {
                this.show_typing_indicator();
            } else {
                this.hide_typing_indicator();
            }
        }
    }

    update_status_panel(data) {
        // Update status panel with real-time data
        if (data.ai_status) {
            $('#ai-status').html(`<i class="indicator ${data.ai_status.connected ? 'green' : 'red'}"></i> ${data.ai_status.status}`);
        }
    }
}
