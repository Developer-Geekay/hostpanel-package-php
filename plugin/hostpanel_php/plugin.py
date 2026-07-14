from hostpanel_php.routes import router


PLUGIN_MANIFEST = {
    "requires_core": [1, 0, 0],
    "repository": "https://github.com/Developer-Geekay/hostpanel-package-php",
    "nav_items": [
        {
            "nav_route": "php",
            "nav_label": "PHP",
            "nav_icon": "code",
            "nav_section": "hosting",
            "nav_section_label": "Hosting",
            "nav_section_order": 30,
            "admin_only": False,
        },
    ],
    "dashboard_blocks": [
        {
            "type": "stat",
            "label": "PHP Sites",
            "icon": "code",
            "endpoint": "php/count",
            "size": "sm",
        },
    ],
    "service": {
        "name": "php",
        "unit": "hostpanel-php-fpm",
        "label": "PHP-FPM 8.4",
        "icon": "code",
        "can_reload": True,
        "config_path": "/opt/hostpanel/plugins/php/conf/php-fpm.conf",
    },
}


routers = [router]
