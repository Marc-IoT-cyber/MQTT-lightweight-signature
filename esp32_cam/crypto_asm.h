#ifndef CRYPTO_ASM_H
#define CRYPTO_ASM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void xor_cipher(uint8_t *data, uint8_t key, int len);
int secure_memcmp(const uint8_t *a, const uint8_t *b, int len);

#ifdef __cplusplus
}
#endif

#endif
