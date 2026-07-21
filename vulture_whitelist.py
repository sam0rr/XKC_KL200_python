"""Reviewed references that Vulture cannot discover statically."""

# These supported public enum members are consumed by downstream applications.
ON_WHEN_DETECTED
OFF_WHEN_DETECTED
ALWAYS_OFF
INACTIVE_WHEN_DETECTED
RELAY

# This parsed-frame field is part of the public structured protocol result.
length
