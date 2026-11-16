# Stage 1: Build Vite React SPA
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency manifests
COPY package*.json ./

# Install dependencies (clean install)
RUN npm install

# Copy application sources
COPY . .

# Build application bundle
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2: Serve with lightweight NGINX
FROM nginx:alpine

# Copy built distribution from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with reverse proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

