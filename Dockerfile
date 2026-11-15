FROM golang:1.22 AS build
WORKDIR /src
COPY . .
ARG VERSION=dev
RUN CGO_ENABLED=0 go build -ldflags "-X main.version=${VERSION}" -o /setlist ./cmd/setlist

FROM gcr.io/distroless/static
COPY --from=build /setlist /setlist
EXPOSE 8080
ENTRYPOINT ["/setlist"]
