# Stage 1: Build Frontend
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependency specifications
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code and compile
COPY . .
RUN npm run build

# Stage 2: Production Server
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=5000

# Install production dependencies only
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Copy server and built frontend from builder stage
COPY server ./server
COPY --from=builder /app/dist ./dist

# Expose port and start
EXPOSE 5000
CMD ["node", "server/server.js"]
