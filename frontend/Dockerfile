# ---- Build stage: compile the Vite app to static files ----
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Vite reads VITE_* values from frontend/.env at build time and bakes them
# into the bundle. These are public client-side values (anon key, API URL).
COPY . .
RUN npm run build

# ---- Serve stage: nginx serving the built static files ----
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
