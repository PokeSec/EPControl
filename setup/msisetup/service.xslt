<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:wix="http://schemas.microsoft.com/wix/2006/wi">
    <xsl:output method="xml" indent="yes" />

    <xsl:strip-space elements="*"/>

    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>

    <xsl:template match="wix:Component[contains(wix:File/@Source,'epcontrol.exe')]">
        <xsl:copy>
            <xsl:apply-templates select="node() | @*"/>
            <wix:ServiceInstall Id="EPC_ServiceInstall"
                                DisplayName="EPControl"
                                Description="EPControl service"
                                Name="EPControl"
                                ErrorControl="normal"
                                Start="auto"
                                Type="ownProcess"
                                Vital="yes"
                                Account="LocalSystem"/>
            <wix:ServiceControl Id="EPC_ServiceControl"
                                Name="EPControl"
                                Start="install"
                                Stop="uninstall"
                                Remove="uninstall"/>
        </xsl:copy>
    </xsl:template>
</xsl:stylesheet>