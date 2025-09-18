# Overview

This is an ERPNext AI Assistant application that provides a natural language interface for interacting with ERPNext databases. The system combines a React-based frontend with an Express backend, integrated with Ollama for AI-powered chat functionality and database operations. Users can ask questions in natural language and receive intelligent responses, with the AI analyzing and executing appropriate ERPNext commands while maintaining safety guardrails.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: React with TypeScript using Vite as the build tool
- **UI Library**: Shadcn/ui components built on Radix UI primitives with Tailwind CSS styling
- **State Management**: TanStack Query for server state management and React hooks for local state
- **Routing**: Wouter for client-side routing
- **Real-time Communication**: WebSocket connection for live chat functionality

## Backend Architecture
- **Framework**: Express.js with TypeScript, running on Node.js
- **API Design**: RESTful endpoints with WebSocket support for real-time chat
- **Data Layer**: Drizzle ORM with PostgreSQL database support
- **Command Execution**: ERPNext service for executing bench commands safely
- **AI Integration**: Ollama service for natural language processing and command generation

## Database Design
- **Primary Database**: PostgreSQL with Drizzle ORM for application data
- **Schema Management**: Automated migrations with drizzle-kit
- **Core Tables**: Users, chat messages, database schema cache, and application settings
- **ERPNext Integration**: Direct command execution against ERPNext instances via bench CLI

## AI and NLP Architecture
- **AI Provider**: Ollama for local LLM inference
- **Command Analysis**: Multi-step process including safety validation, command generation, and execution confirmation
- **Context Management**: Database schema scanning and caching for informed AI responses
- **Safety Features**: Destructive operation detection, confirmation workflows, and safe mode enforcement

## Real-time Communication
- **WebSocket Server**: Integrated with Express HTTP server for bidirectional communication
- **Message Types**: Chat messages, command confirmations, database scans, and settings updates
- **Connection Management**: Client connection tracking with automatic reconnection support

## Security and Safety
- **Command Validation**: Input sanitization and command structure validation before execution
- **Safe Mode**: Configurable safety restrictions for destructive operations
- **Confirmation Flows**: User approval required for potentially dangerous database operations
- **Timeout Protection**: Command execution timeouts to prevent hanging operations

# External Dependencies

## Core Infrastructure
- **Database**: PostgreSQL via Neon serverless database (@neondatabase/serverless)
- **ORM**: Drizzle ORM for database operations and schema management
- **Build Tools**: Vite for frontend bundling, esbuild for backend compilation

## AI and Machine Learning
- **Ollama**: Local LLM server for natural language processing and command generation
- **Models**: Configurable model support (default: llama2) for different AI capabilities

## UI and Styling
- **Radix UI**: Comprehensive set of unstyled, accessible UI components
- **Tailwind CSS**: Utility-first CSS framework for responsive design
- **Lucide React**: Icon library for consistent visual elements

## Development and Deployment
- **TypeScript**: Full-stack type safety and improved developer experience
- **ESLint/Prettier**: Code quality and formatting tools
- **Replit Integration**: Development environment plugins and optimizations

## ERPNext Integration
- **Bench CLI**: Direct integration with ERPNext's command-line interface
- **Frappe Framework**: Underlying framework commands for database operations and system management
- **Site Management**: Multi-site support with configurable site targeting