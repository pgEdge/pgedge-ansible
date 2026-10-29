# This Makefile helps to build, install or publish the Ansible
# collection on the Galaxy platform.
#
# The collection's version is taken from the first of these that gives one:
#
#   1. VERSION=x.y.z on the command line or in the environment.
#   2. "git describe", when this directory is the top of its own git checkout.
#   3. .git_archival.txt, which "git archive" fills in when it exports the
#      tree. GitHub builds its release tarballs and "Download ZIP" files this
#      way, so a downloaded source tree still knows its version.
#
# A tree with none of these, such as a plain copy of the files, stops the build
# rather than producing a tarball with a made-up version. Pass VERSION=x.y.z.
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

# git describe walks up the directory tree, so a source tarball unpacked inside
# some other repository would report that repository's tags. Only trust git when
# this directory is the top of the checkout. --always is left out on purpose: a
# bare commit hash is not a version Galaxy accepts.
ifeq ($(realpath $(shell git -C $(DIR) rev-parse --show-toplevel 2>/dev/null)),$(realpath $(DIR)))
GIT_VERSION := $(shell git -C $(DIR) describe --tags --dirty --match 'v[0-9]*' 2>/dev/null | sed 's/^v//')
endif

# In a checkout the file still holds its unexpanded $Format placeholder, which
# the pattern below rejects, so only an exported tree yields a version here.
ARCHIVE_VERSION := $(shell sed -n 's/^v//; /^[0-9]/p' $(DIR)/.git_archival.txt 2>/dev/null)

VERSION ?= $(or $(GIT_VERSION),$(ARCHIVE_VERSION))
TARGET := $(DIR)/pgedge-platform-$(VERSION).tar.gz

.PHONY: build clean install

build: $(TARGET)

# Every file the collection ships, not only its task files: a template, a
# script, a doc page, or a meta file edited on its own changes the collection
# just as much. A dirty tree keeps the same version string across edits, so the
# tarball's name alone never forces a rebuild.
#
# The directories are listed too, not only the files in them. A deleted file
# is no longer there for make to compare, but removing it touches its parent
# directory, so the tarball still rebuilds without it. The top-level directory
# is left out on purpose: writing galaxy.yml and the tarball there touches it on
# every build, and nothing would ever be up to date.
SOURCES := $(shell find $(DIR)/roles $(DIR)/meta $(DIR)/docs $(DIR)/sample-playbooks) \
	$(DIR)/galaxy.template.yml $(DIR)/README.md $(DIR)/SECURITY.md \
	$(DIR)/mkdocs.yml $(DIR)/Makefile

$(TARGET): $(SOURCES)
	@test -n "$(VERSION)" || { \
		echo "Cannot tell which version this is: no git tags and no .git_archival.txt." >&2; \
		echo "Pass it explicitly, for example: make build VERSION=2.1.0" >&2; \
		exit 1; }
	sed -E 's/version:.*/version: "$(VERSION)"/g' $(DIR)/galaxy.template.yml > $(DIR)/galaxy.yml
	ansible-galaxy collection build --force $(DIR)

clean:
	rm -f $(DIR)/galaxy.yml
	rm -f $(TARGET)

install: build
	ansible-galaxy collection install $(TARGET) --force
