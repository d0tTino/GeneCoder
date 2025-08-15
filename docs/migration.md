# Migration Guide

## Channel attribute rename

The `Channel.error_rate` attribute has been renamed to `Channel.substitution_prob`.
Accessing or setting `error_rate` still works but raises a `DeprecationWarning` and
will be removed in a future release. Update any code that relies on `error_rate`
to use `substitution_prob` instead.
