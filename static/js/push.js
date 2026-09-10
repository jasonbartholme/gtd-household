(function () {
    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    const toggleLinks = document.querySelectorAll('.js-push-toggle-link');
    const testLinks = document.querySelectorAll('.js-push-test-link');
    const vapidPublicKey = document.querySelector('meta[name="vapid-public-key"]')?.content;

    if (!toggleLinks.length || !('serviceWorker' in navigator) || !('PushManager' in window) || !vapidPublicKey) {
        toggleLinks.forEach(function (el) { el.closest('li')?.remove(); });
        testLinks.forEach(function (el) { el.closest('li')?.remove(); });
        return;
    }

    function setUiState(isSubscribed) {
        toggleLinks.forEach(function (el) {
            el.textContent = isSubscribed ? 'Disable Notifications' : 'Enable Notifications';
        });
        testLinks.forEach(function (el) {
            el.classList.toggle('d-none', !isSubscribed);
        });
    }

    async function getRegistration() {
        return navigator.serviceWorker.register('/sw.js');
    }

    async function subscribeToPush() {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            alert('Notification permission was not granted.');
            return;
        }
        const registration = await getRegistration();
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });
        await fetch('/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subscription.toJSON())
        });
        setUiState(true);
    }

    async function unsubscribeFromPush() {
        const registration = await getRegistration();
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
            await fetch('/push/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint: subscription.endpoint })
            });
            await subscription.unsubscribe();
        }
        setUiState(false);
    }

    toggleLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const isSubscribed = link.textContent.trim() === 'Disable Notifications';
            (isSubscribed ? unsubscribeFromPush() : subscribeToPush()).catch(function (err) {
                console.error('Push subscription toggle failed:', err);
            });
        });
    });

    testLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            fetch('/push/test', { method: 'POST' }).catch(function (err) {
                console.error('Push test failed:', err);
            });
        });
    });

    getRegistration()
        .then(function (registration) {
            return registration.pushManager.getSubscription();
        })
        .then(function (subscription) {
            setUiState(!!subscription);
        })
        .catch(function (err) {
            console.error('Service worker registration failed:', err);
        });
})();
