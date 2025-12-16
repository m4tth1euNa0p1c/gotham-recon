# Build Stage
FROM golang:alpine AS builder
RUN apk add --no-cache git
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Runtime Stage
FROM alpine:3.19
RUN apk add --no-cache ca-certificates bind-tools
COPY --from=builder /go/bin/subfinder /usr/local/bin/subfinder

ENTRYPOINT ["subfinder"]
CMD ["-h"]
