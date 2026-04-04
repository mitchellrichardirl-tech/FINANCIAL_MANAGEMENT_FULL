FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Bake in a relative path so requests go to nginx, not direct to backend
ENV VITE_API_URL=/api
RUN npm run build
RUN npm run docs

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /app/docs /usr/share/nginx/html/docs
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80