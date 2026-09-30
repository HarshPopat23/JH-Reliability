# Official setup: index schemas during the image build, then serve the indexed registry.
FROM ghcr.io/sourcemeta/one:6.7
COPY one.json .
COPY schemas schemas
RUN sourcemeta one.json
