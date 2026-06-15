from setuptools import find_packages, setup


setup(
    name="hostpanel-php",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["fastapi", "pydantic"],
    entry_points={
        "hostpanel.modules": [
            "php = hostpanel_php.plugin",
        ],
        "hostpanel.setup": [
            "hostpanel-php = hostpanel_php.lifecycle:on_install",
        ],
        "hostpanel.lifecycle": [
            "hostpanel-php = hostpanel_php.lifecycle:pre_uninstall",
        ],
        "hostpanel.hooks.on_startup": [
            "hostpanel-php = hostpanel_php.lifecycle:on_startup",
        ],
        "hostpanel.hooks.user_delete": [
            "hostpanel-php = hostpanel_php.lifecycle:on_user_delete",
        ],
        "hostpanel.hooks.domain_delete": [
            "hostpanel-php = hostpanel_php.lifecycle:on_domain_delete",
        ],
        "hostpanel.hooks.ssl_cert_imported": [
            "hostpanel-php = hostpanel_php.lifecycle:on_ssl_cert_imported",
        ],
        "hostpanel.hooks.ssl_cert_deleted": [
            "hostpanel-php = hostpanel_php.lifecycle:on_ssl_cert_deleted",
        ],
    },
)
