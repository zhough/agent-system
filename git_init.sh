#!/bin/bash
source .git_init.sh

eval "$(ssh-agent -s)"
ssh-add ~/zhou/.ssh/id_ed25519