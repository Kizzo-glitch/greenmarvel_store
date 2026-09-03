/**
 * ============================================================
 * TikTok Events Helper — window.TT
 * ============================================================
 * Loaded once in base1.html AFTER the base TikTok Pixel snippet.
 * Exposes window.TT with one function per standard event.
 * 
 * Usage examples:
 *     TT.viewContent({ id: 1, name: 'Vitality Spray', price: 130 });
 *     TT.addToCart({ id: 1, name: 'Vitality Spray', price: 130 }, 2);
 *     TT.initiateCheckout({ items: [...], total: 260 });
 *     TT.addPaymentInfo({ items: [...], total: 260 });
 *     TT.completePayment({ id: 42, items: [...], total: 260 });
 * 
 * All events:
 *   - Auto-include ZAR currency
 *   - Auto-brand as "Marvelously Green"
 *   - Include unique event_id for server-side deduplication
 *   - Optionally POST to Django /tiktok/track/ endpoint for
 *     server-side Events API (iOS 14+ / ad-blocker resilience)
 * ============================================================
 */

(function() {
    'use strict';

    // Guard: don't crash the site if TikTok pixel didn't load (ad blockers, offline)
    if (typeof ttq === 'undefined') {
        console.warn('[TikTok] Pixel (ttq) not loaded — events will not fire client-side');
        // Still expose window.TT with no-op functions so template calls don't error
        window.TT = {
            viewContent: function() {},
            addToCart: function() {},
            initiateCheckout: function() {},
            addPaymentInfo: function() {},
            completePayment: function() {},
        };
        return;
    }

    // Config — change these if your setup differs
    const CONFIG = {
        currency: 'ZAR',
        brand: 'Marvelously Green',
        contentCategory: 'Hair Care',
        // Server-side Events API endpoint (Django view)
        // Set to null to disable server-side firing
        serverEndpoint: '/tiktok/track/',
        debug: false,  // Set true to log every event to console
    };

    // Utility: generate a unique event ID for client<>server deduplication
    // TikTok will dedupe events with matching event_id across sources
    function generateEventId() {
        return 'e_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Utility: coerce price-like value to a number
    function toPrice(v) {
        const n = parseFloat(v);
        return isNaN(n) ? 0 : n;
    }

    // Utility: get CSRF token from cookie (Django standard)
    function getCsrfToken() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : null;
    }

    // Build a TikTok-compliant content object from a product
    function buildContent(product, quantity) {
        return {
            content_id: String(product.id),
            content_type: 'product',
            content_name: product.name || '',
            content_category: product.category || CONFIG.contentCategory,
            price: toPrice(product.price),
            quantity: parseInt(quantity) || 1,
            brand: CONFIG.brand,
        };
    }

    // Fire the client-side event via ttq
    function fireClientSide(eventName, payload, eventId) {
        try {
            ttq.track(eventName, payload, { event_id: eventId });
            if (CONFIG.debug) {
                console.log('[TikTok:client] ' + eventName, { eventId, payload });
            }
        } catch (err) {
            console.warn('[TikTok:client] ' + eventName + ' failed:', err);
        }
    }

    // Optionally fire the same event server-side (via Django endpoint)
    // Doesn't await — fire and forget so it doesn't block UI
    function fireServerSide(eventName, payload, eventId) {
        if (!CONFIG.serverEndpoint) return;

        try {
            fetch(CONFIG.serverEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken() || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify({
                    event: eventName,
                    event_id: eventId,
                    data: payload,
                }),
                // keepalive lets the request finish even if the user navigates away
                keepalive: true,
            }).catch(function(err) {
                if (CONFIG.debug) {
                    console.warn('[TikTok:server] ' + eventName + ' failed:', err);
                }
            });
        } catch (err) {
            // Silently ignore — client-side already fired
        }
    }

    // Fire event to both client + server
    function fireEvent(eventName, payload) {
        const eventId = generateEventId();
        fireClientSide(eventName, payload, eventId);
        fireServerSide(eventName, payload, eventId);
        return eventId;
    }

    // ============================================
    // PUBLIC API — window.TT
    // ============================================
    window.TT = {

        /**
         * Fire when user views a product detail page.
         * @param {Object} product - { id, name, price, category? }
         */
        viewContent: function(product) {
            if (!product || !product.id) {
                console.warn('[TikTok] viewContent called without valid product');
                return;
            }
            const content = buildContent(product, 1);
            const payload = {
                contents: [content],
                content_type: 'product',
                value: content.price,
                currency: CONFIG.currency,
            };
            fireEvent('ViewContent', payload);
        },

        /**
         * Fire when user adds a product to cart.
         * @param {Object} product - { id, name, price, category? }
         * @param {number} quantity - defaults to 1
         */
        addToCart: function(product, quantity) {
            if (!product || !product.id) {
                console.warn('[TikTok] addToCart called without valid product');
                return;
            }
            const qty = quantity || 1;
            const content = buildContent(product, qty);
            const payload = {
                contents: [content],
                content_type: 'product',
                value: content.price * content.quantity,
                currency: CONFIG.currency,
            };
            fireEvent('AddToCart', payload);
        },

        /**
         * Fire when user reaches the cart summary / checkout page.
         * @param {Object} cart - { items: [{id, name, price, quantity}, ...], total }
         */
        initiateCheckout: function(cart) {
            if (!cart || !cart.items || cart.items.length === 0) {
                if (CONFIG.debug) {
                    console.warn('[TikTok] initiateCheckout skipped — empty cart');
                }
                return;
            }
            const contents = cart.items.map(function(item) {
                return buildContent(item, item.quantity);
            });
            const value = toPrice(cart.total) || contents.reduce(function(sum, c) {
                return sum + (c.price * c.quantity);
            }, 0);
            const payload = {
                contents: contents,
                content_type: 'product',
                value: value,
                currency: CONFIG.currency,
            };
            fireEvent('InitiateCheckout', payload);
        },

        /**
         * Fire when user submits billing/shipping information.
         * @param {Object} cart - { items: [...], total }
         */
        addPaymentInfo: function(cart) {
            if (!cart || !cart.items || cart.items.length === 0) return;
            const contents = cart.items.map(function(item) {
                return buildContent(item, item.quantity);
            });
            const value = toPrice(cart.total) || contents.reduce(function(sum, c) {
                return sum + (c.price * c.quantity);
            }, 0);
            const payload = {
                contents: contents,
                content_type: 'product',
                value: value,
                currency: CONFIG.currency,
            };
            fireEvent('AddPaymentInfo', payload);
        },

        /**
         * Fire when the order confirmation page loads (payment succeeded).
         * @param {Object} order - { id, items: [...], total, shipping? }
         */
        completePayment: function(order) {
            if (!order || !order.items || order.items.length === 0) {
                console.warn('[TikTok] completePayment called without valid order');
                return;
            }
            const contents = order.items.map(function(item) {
                return buildContent(item, item.quantity);
            });
            const value = toPrice(order.total) || contents.reduce(function(sum, c) {
                return sum + (c.price * c.quantity);
            }, 0);
            const payload = {
                contents: contents,
                content_type: 'product',
                value: value,
                currency: CONFIG.currency,
                order_id: String(order.id),
            };
            fireEvent('CompletePayment', payload);
        },

        // Utility exposed for debugging
        _config: CONFIG,
    };

    if (CONFIG.debug) {
        console.log('[TikTok] Events helper loaded — window.TT ready', CONFIG);
    }
})();