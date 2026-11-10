# The Independent Check Rule: letters of 10 November 2026

On 10 November 2026 sebbi.pro (Monop Content) wrote to bodies responsible for evidence law and AI standards, proposing a short, method-neutral rule:

> A record that only its owner can vouch for carries no presumption of integrity. A record that anyone can check independently is presumed unaltered since its independent timestamp.

Every letter is published here in full, exactly as sent. Each file's SHA-256 fingerprint was timestamped into Bitcoin through OpenTimestamps before the letter was sent, so neither the text nor the date can be changed afterwards.

| Letter | Jurisdiction | Sent to | SHA-256 | Bitcoin timestamp receipt |
|---|---|---|---|---|
| [00-uk-ministry-of-justice-and-justice-committee.txt](00-uk-ministry-of-justice-and-justice-committee.txt) | England and Wales | Ministry of Justice (computer evidence review); House of Commons Justice Committee | `ce4ceff1a1ad45eb0593d7152e820df2bce58ae8de8ab8294468c11e80956fe2` | [NT-RAXJ-UEL7](https://sebbi.pro/n/NT-RAXJ-UEL7) |
| [01-us-judicial-conference-rules-committee.txt](01-us-judicial-conference-rules-committee.txt) | United States | Committee on Rules of Practice and Procedure, Judicial Conference of the United States (for the Advisory Committee on Evidence Rules) | `d426a29800d09e4dfb44b94c7b8086431e4c7155f030d1ec0fd0fb818aca2f13` | [NT-U45T-QFJY](https://sebbi.pro/n/NT-U45T-QFJY) |
| [02-us-nist.txt](02-us-nist.txt) | United States | National Institute of Standards and Technology, AI programme | `2a1cf4a02c6395cac23ee9e6d10d4ed90e897d88b7a1417acea2b050b1220557` | [NT-EAKL-ZKZ3](https://sebbi.pro/n/NT-EAKL-ZKZ3) |
| [03-eu-ai-office.txt](03-eu-ai-office.txt) | European Union | European AI Office, European Commission (DG CNECT) | `cf5037210c36e2f8bf68b7348bb13f487fe22ca51bd5838564a646cfd1476fd3` | [NT-CWTP-KBGP](https://sebbi.pro/n/NT-CWTP-KBGP) |
| [04-cen-cenelec-jtc21.txt](04-cen-cenelec-jtc21.txt) | European Union | CEN-CENELEC Joint Technical Committee 21 (Artificial Intelligence), Secretariat (returned undelivered on 10 November 2026: the published contact address is no longer valid; to be re-sent through a national standards body) | `09d4bb5236c7a3131345295be08026ef37d5478562f3c19b01b21a48a29df39a` | [NT-QJ7C-B43X](https://sebbi.pro/n/NT-QJ7C-B43X) |
| [05-uk-law-commission.txt](05-uk-law-commission.txt) | England and Wales | Law Commission of England and Wales, Criminal Law team | `72b57f7b5f9c2d67a5d3eb08442314de892d7f14152c2ac1716081ec86684a2d` | [NT-3WFL-HJEM](https://sebbi.pro/n/NT-3WFL-HJEM) |
| [06-scottish-law-commission.txt](06-scottish-law-commission.txt) | Scotland | Scottish Law Commission | `d93866675f8b4c46d572a78f5a60f24cea898bdd1a4d90af73ca2dcd707a5bdf` | [NT-MCZF-RH2D](https://sebbi.pro/n/NT-MCZF-RH2D) |
| [07-uk-ico.txt](07-uk-ico.txt) | United Kingdom | Information Commissioner's Office, agentic AI call for evidence | `250f3cf89c1356d36942fb60914f30e5f807f13a53d19dcef552b2b58be1268f` | [NT-36JM-M4DR](https://sebbi.pro/n/NT-36JM-M4DR) |
| [08-uncitral.txt](08-uncitral.txt) | International | UNCITRAL Secretariat (for Working Group IV, Electronic Commerce) | `2297515afda662689bd76c0153132de2db737d0a54ab588df321111dffcba97d` | [NT-J5R8-R3NB](https://sebbi.pro/n/NT-J5R8-R3NB) |
| [09-india-law-commission.txt](09-india-law-commission.txt) | India | Law Commission of India | `2833e2f6f9888ac6396a26397ef659bf9aab0711f1c5089db28cd647d415a601` | [NT-PR5P-LDRJ](https://sebbi.pro/n/NT-PR5P-LDRJ) |
| [10-australia-alrc.txt](10-australia-alrc.txt) | Australia | Australian Law Reform Commission | `4915e2bf954663ac9ef5fd46de435c87ba67d62c59a98fa8c521a5e9ac3e3d50` | [NT-UWS2-T722](https://sebbi.pro/n/NT-UWS2-T722) |
| [11-new-zealand-law-commission.txt](11-new-zealand-law-commission.txt) | New Zealand | Te Aka Matua o te Ture | Law Commission | `56b5ffc864bc9ee65a2a299987d56852abe0298dc202ae30668db2320efe6b43` | [NT-9JD9-JSVZ](https://sebbi.pro/n/NT-9JD9-JSVZ) |
| [12-hong-kong-law-reform-commission.txt](12-hong-kong-law-reform-commission.txt) | Hong Kong SAR, China | Law Reform Commission of Hong Kong | `05a4284eb4c761f0ae131a474ed05049f5139281ac4e46c638689ee970d461e7` | [NT-E2UP-7DNX](https://sebbi.pro/n/NT-E2UP-7DNX) |

## Check it yourself

```
sha256sum 03-eu-ai-office.txt
```

The output must equal the fingerprint in the table. Each receipt gives the OpenTimestamps proof for that fingerprint, which can be verified against the Bitcoin blockchain with the open-source OpenTimestamps client and nothing from sebbi.pro. Proofs confirm in a Bitcoin block within a few hours of sending.

## The rule and the evidence

- The rule, six questions for any party relying on a log, and a model clause: https://sebbi.pro/independent-check-rule
- State of the Art Notice: https://sebbi.pro/.well-known/state-of-the-art-logging.json
- Editable Log Test: https://sebbi.pro/log-test
