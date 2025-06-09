# docker.io/blindmuaddib/beethoven
# --- Stage 1: Build the assets ---
# Use a Node.js image as a temporary "builder" container.
FROM node:20-slim AS builder

WORKDIR /app

# Copy package.json and install dependencies
COPY package.json ./
COPY package-lock.json ./
RUN npm install -g npm@11.4.1 && npm ci

# Copy HTML, CSS and JS source files
RUN mkdir -p /app/www
COPY www/ /app/www

# --- Stage 2 ---
# Use a small, official Nginx image.
FROM docker.io/library/nginx:1.28.0-alpine

# Copy the static files from the 'builder' stage into the Nginx public directory.
RUN rm -rf /usr/share/nginx/html/*
COPY --from=builder /app/www /usr/share/nginx/html

# Copy a custom Nginx configuration file. This is crucial for single-page applications.
COPY www/nginx.conf /etc/nginx/conf.d/default.conf

# Test the configuration then reload on success
RUN nginx -t

# Expose port 80
EXPOSE 80
