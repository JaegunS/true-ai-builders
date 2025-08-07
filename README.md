# True AI Builders

AI-powered tools for news scraping, profile analysis, and business intelligence.

## Quick Start

```bash
# Install dependencies
pnpm install

# Build the project
pnpm run build

# Run in development mode
pnpm run dev

# Run the built application
pnpm start
```

## Project Structure

```
src/
├── services/
│   ├── news.ts        # RSS feeds, web search, email
│   └── profiles.ts    # LinkedIn scraping, RAG, templates
├── utils/
│   └── logger.ts      # Logging utility
└── index.ts           # Main entry point
```

## Development

- `pnpm run dev` - Start development server with hot reload
- `pnpm run build` - Build TypeScript to JavaScript
- `pnpm run start` - Run the built application
- `pnpm run test` - Run tests
- `pnpm run lint` - Run ESLint

## Environment Variables

Create a `.env` file in the root directory:

```env
# Add your environment variables here
NODE_ENV=development
```
