# This Makefile helps to build, install or publish the Ansible
# collection on the Galaxy platform.
#
# Target version can be passed with the PGEDGE_ANSIBLE_VERSION variable.
# The default version is taken from the VERSION file content.
#
# Build the collection:
#
#   make build
#
# Clean up the generated files:
#
#   make clean
#
# Build and install the collection:
#
#   make install
#

VERSION ?= $(shell { git describe --tags --always --dirty 2>/dev/null || echo "0.0.0-dev"; } | sed 's/^v//')
DIR := $(dir $(abspath $(firstword $(MAKEFILE_LIST))))
TARGET := $(DIR)/pgedge-platform-$(VERSION).tar.gz

.PHONY: build clean install

build: $(TARGET)

$(TARGET): $(shell find $(DIR)/roles -name '*.yaml')
	sed -E 's/version:.*/version: "$(VERSION)"/g' $(DIR)/galaxy.template.yml > $(DIR)/galaxy.yml
	ansible-galaxy collection build --force $(DIR)

clean:
	rm -f $(DIR)/galaxy.yml
	rm -f $(TARGET)

install: build
	ansible-galaxy collection install $(TARGET) --force
