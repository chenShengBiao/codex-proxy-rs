//! 账号出站代理连接、容量与直连回退配置，诊断及普通管理投影不暴露凭据

use std::fmt;
use url::Url;

#[derive(Clone, PartialEq, Eq, Hash)]
pub struct OutboundProxy {
    url: Url,
    max_websocket_connections: u32,
    allow_direct_fallback: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[error("invalid outbound proxy; expected http, https, socks5 or socks5h URL with a host and port")]
pub struct InvalidOutboundProxy;

impl OutboundProxy {
    pub fn parse(value: &str) -> Result<Self, InvalidOutboundProxy> {
        if value.len() > 4096 || value.chars().any(char::is_control) {
            return Err(InvalidOutboundProxy);
        }
        let url = Url::parse(value).map_err(|_| InvalidOutboundProxy)?;
        if !matches!(url.scheme(), "http" | "https" | "socks5" | "socks5h")
            || url.host_str().is_none()
            || url.port_or_known_default().is_none_or(|port| port == 0)
            || !matches!(url.path(), "" | "/")
            || url.query().is_some()
            || url.fragment().is_some()
        {
            return Err(InvalidOutboundProxy);
        }
        Ok(Self {
            url,
            max_websocket_connections: 0,
            allow_direct_fallback: false,
        })
    }

    /// 此出口的上游 WebSocket 容量，零值表示不限制
    #[must_use]
    pub fn with_max_websocket_connections(mut self, limit: u32) -> Self {
        self.max_websocket_connections = limit;
        self
    }

    #[must_use]
    pub const fn max_websocket_connections(&self) -> u32 {
        self.max_websocket_connections
    }

    /// 仅原生模型请求可在确认未发送的代理连接故障后申请直连
    #[must_use]
    pub fn with_allow_direct_fallback(mut self, allow: bool) -> Self {
        self.allow_direct_fallback = allow;
        self
    }

    #[must_use]
    pub const fn allow_direct_fallback(&self) -> bool {
        self.allow_direct_fallback
    }

    #[must_use]
    pub fn expose_url(&self) -> &str {
        self.url.as_str()
    }

    #[must_use]
    pub fn endpoint(&self) -> String {
        let mut url = self.url.clone();
        let _ = url.set_username("");
        let _ = url.set_password(None);
        url.to_string()
    }
}

impl fmt::Debug for OutboundProxy {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("OutboundProxy(<redacted>)")
    }
}
