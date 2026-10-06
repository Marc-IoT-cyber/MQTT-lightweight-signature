/*
 * crypto_asm.S - Fonctions assembleur Xtensa pour ESP32-CAM
 * Projet : Signature électronique légère pour MQTT
 */

    .text

/* ============================================================
 * void xor_cipher(uint8_t *data, uint8_t key, int len)
 *   a2 = data, a3 = key, a4 = len
 * ============================================================ */
    .global xor_cipher
    .type   xor_cipher, @function
    .align  4

xor_cipher:
    entry   a1, 32
    beqz    a4, .Lxor_end
    movi    a5, 0

.Lxor_loop:
    l8ui    a6, a2, 0
    xor     a6, a6, a3
    s8i     a6, a2, 0
    addi    a2, a2, 1
    addi    a5, a5, 1
    blt     a5, a4, .Lxor_loop

.Lxor_end:
    retw

    .size   xor_cipher, . - xor_cipher


/* ============================================================
 * int secure_memcmp(const uint8_t *a, const uint8_t *b, int len)
 * ============================================================ */
    .global secure_memcmp
    .type   secure_memcmp, @function
    .align  4

secure_memcmp:
    entry   a1, 32
    movi    a5, 0
    movi    a6, 0

.Lcmp_loop:
    bge     a5, a4, .Lcmp_end
    l8ui    a7, a2, 0
    l8ui    a8, a3, 0
    xor     a7, a7, a8
    or      a6, a6, a7
    addi    a2, a2, 1
    addi    a3, a3, 1
    addi    a5, a5, 1
    j       .Lcmp_loop

.Lcmp_end:
    movi    a7, 0
    movnez  a7, a6, a6
    movi    a2, 0
    movnez  a2, a7, a7
    retw

    .size   secure_memcmp, . - secure_memcmp
