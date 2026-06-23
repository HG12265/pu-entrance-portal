import React from "react";
import "./UniversityHeader.css";

const UniversityHeader = () => {
  return (
    <header className="university-header">
      <div className="header-left">
        <img
          src="/assets/periyar-logo.png"
          alt="Periyar University Logo"
          className="university-logo"
        />
        <div className="university-title-block">
          <div className="tamil-container">
            <h1 className="tamil-title">பெரியார் பல்கலைக்கழகம்</h1>
            <span className="tamil-subtitle">அரசு பல்கலைக்கழகம், சேலம்.</span>
          </div>
          <h2 className="english-title">PERIYAR UNIVERSITY</h2>
          <div className="university-meta">
            <span>State University</span>
            <span className="meta-separator">•</span>
            <span>NAAC 'A++' Grade</span>
            <span className="meta-separator">•</span>
            <span>NIRF Rank 94</span>
            <br />
            <span>State Public University Rank 40</span>
            <span className="meta-separator">•</span>
            <span>SDG Institutions Rank Band: 11-50</span>
            <br />
            <span>Salem - 636 011, Tamil Nadu, India.</span>
          </div>
        </div>
      </div>

      <div className="header-right">
        <div className="portrait-wrap">
          <img
            src="/assets/periyar-portrait.png"
            alt="Thanthai Periyar Sketch"
            className="university-portrait"
          />
        </div>
      </div>
    </header>
  );
};

export default UniversityHeader;
