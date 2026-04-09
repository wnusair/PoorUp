FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_ENABLE_HOST_DEBUG_TOOLS=true
ENV VITE_ENABLE_HOST_DEBUG_TOOLS=$VITE_ENABLE_HOST_DEBUG_TOOLS

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80