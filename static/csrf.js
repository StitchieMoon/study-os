(function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute("content") : "";
    if (!token) {
        return;
    }

    function addToken(form) {
        if (!form || (form.method || "").toLowerCase() !== "post") {
            return;
        }
        if (form.querySelector('input[name="_csrf_token"]')) {
            return;
        }
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = "_csrf_token";
        input.value = token;
        form.appendChild(input);
    }

    function addTokens(root) {
        var forms = (root || document).querySelectorAll("form");
        for (var i = 0; i < forms.length; i += 1) {
            addToken(forms[i]);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            addTokens(document);
        });
    } else {
        addTokens(document);
    }

    document.addEventListener("submit", function (event) {
        addToken(event.target);
    }, true);

    var nativeFetch = window.fetch;
    if (nativeFetch) {
        window.fetch = function (input, init) {
            init = init || {};
            var method = (
                init.method ||
                (input && input.method) ||
                (init.body ? "POST" : "GET")
            ).toUpperCase();
            if (method !== "GET" && method !== "HEAD") {
                var headers = new Headers(init.headers || {});
                if (!headers.has("X-CSRF-Token")) {
                    headers.set("X-CSRF-Token", token);
                }
                init.headers = headers;
            }
            return nativeFetch.call(this, input, init);
        };
    }
})();
