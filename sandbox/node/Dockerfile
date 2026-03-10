FROM node:20-slim

RUN npm install -g jest vitest supertest

RUN useradd --create-home --uid 1000 sandbox || true
USER node
WORKDIR /workspace

# Default: run jest
CMD ["npx", "jest", "--verbose"]
