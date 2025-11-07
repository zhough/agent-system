#!/bin/bash
source ~/.bashrc

eval "$(ssh-agent -s)"
ssh-add ~/zhou/.ssh/id_ed25519