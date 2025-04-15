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

DIR := $(dir $(abspath $(firstword $(MAKEFILE_LIST))))
PGEDGE_ANSIBLE_VERSION ?= $(shell cat $(DIR)/VERSION | head -n 1)
TARGET := $(DIR)/pgedge-platform-$(PGEDGE_ANSIBLE_VERSION).tar.gz

.PHONY: build clean install

build: $(TARGET)

$(TARGET): $(shell find $(DIR)/roles -name '*.yaml')
	sed -E 's/version:.*/version: "$(PGEDGE_ANSIBLE_VERSION)"/g' $(DIR)/galaxy.template.yml > $(DIR)/galaxy.yml
	ansible-galaxy collection build --force $(DIR)

clean:
	rm -f $(DIR)/galaxy.yml
	rm -f $(DIR)/pgedge-platform-$(PGEDGE_ANSIBLE_VERSION).tar.gz

install: build
	ansible-galaxy collection install $(DIR)/pgedge-platform-$(PGEDGE_ANSIBLE_VERSION).tar.gz --force
