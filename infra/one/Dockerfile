# Official setup: index schemas during the image build, then serve the indexed registry.
FROM ghcr.io/sourcemeta/one:6.7@sha256:0a68085e2842b461d06518c145a209132b4fbcdb9ef76088645466787f22ba8f
COPY one.json .
COPY schemas schemas
RUN sourcemeta one.json
