# Security Notes

GeneCoder encrypts data using AES-GCM with a random nonce. Previous releases also allowed XOR-based encryption for legacy reasons. The XOR branch is now deprecated.

Using data that is not prefixed with the `AESGCM1` header triggers a `DeprecationWarning` and will be removed in a future release. Ensure all encrypted files use AES-GCM.
