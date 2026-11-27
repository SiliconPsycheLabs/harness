"""The browser tools: the agent works in the accounting application through its own pages, as a person does. A real
browser (Chromium, driven by Playwright) is opened on the run's database, already signed in, on the list of suppliers.
Each tool acts on an element by its kind and its name exactly as the page shows them, then gives the page back as a
short list of what can be clicked or filled."""
import json

from harness.companies import acme_odoo

START = "/web#action=account.res_partner_action_supplier&model=res.partner&view_type=list"
KINDS = ("button", "link", "row", "menu item")
SCAN = """() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = e => {
    let n = e.getAttribute('aria-label') || '';
    if (!n && e.id) { const l = document.querySelector('label[for="' + e.id + '"]'); if (l) n = l.innerText; }
    if (!n && e.tagName !== 'INPUT' && e.tagName !== 'TEXTAREA') n = (e.innerText || '').trim().split('\\n')[0];
    if (!n) n = e.getAttribute('placeholder') || e.getAttribute('title') || e.getAttribute('data-tooltip') || e.getAttribute('name') || '';
    if (!n) { const ic = e.querySelector('i.fa, i.oi'); if (ic) n = 'icon ' + [...ic.classList].filter(c => c.startsWith('fa-') || c.startsWith('oi-')).map(c => c.slice(3)).join(' '); }
    return n.replace(/\\s+/g, ' ').trim().slice(0, 60);
  };
  document.querySelectorAll('[data-hx]').forEach(e => e.removeAttribute('data-hx'));
  const modal = document.querySelector('.modal.show, .o_dialog .modal');
  const roots = modal ? [modal] : [...document.querySelectorAll('.o_action_manager, .o-dropdown--menu, .dropdown-menu.show')];
  const out = []; let i = 0; const seen = new Set();
  for (const root of roots) for (const e of root.querySelectorAll('button, a, [role=menuitem], .dropdown-item, input:not([type=hidden]), textarea, select, tr.o_data_row, .o_kanban_record')) {
    if (!vis(e) || e.hasAttribute('data-hx') || e.disabled) continue;
    const tag = e.tagName;
    let kind = tag === 'TR' || e.classList.contains('o_kanban_record') ? 'row' : (tag === 'INPUT' && !['checkbox', 'radio', 'button', 'submit'].includes(e.type)) || tag === 'TEXTAREA' || tag === 'SELECT' ? 'field'
      : e.getAttribute('role') === 'menuitem' || e.classList.contains('dropdown-item') ? 'menu item' : tag === 'A' ? 'link' : 'button';
    if (tag === 'INPUT' && ['checkbox', 'radio'].includes(e.type)) continue;
    let name = kind === 'row' ? ((e.querySelector('td.o_data_cell, .o_kanban_record_title, strong') || e).innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60) : label(e);
    if (!name || seen.has(kind + '|' + name)) continue;
    seen.add(kind + '|' + name);
    e.setAttribute('data-hx', String(i));
    out.push({i: i++, kind, name, value: kind === 'field' ? (e.value || '') : null});
  }
  const crumb = [...document.querySelectorAll('.o_breadcrumb .breadcrumb-item, .o_breadcrumb .o_last_breadcrumb_item, .o_breadcrumb span.text-truncate')].map(e => e.innerText.trim()).filter(Boolean);
  return {title: (modal ? 'Dialog: ' + ((modal.querySelector('.modal-title') || {}).innerText || '') + ' ' + ((modal.querySelector('.modal-body') || {}).innerText || '').slice(0, 200) : crumb.join(' / ')) || document.title, items: out};
}"""


def page(h):
    if getattr(h, "_page", None) is None:
        from playwright.sync_api import sync_playwright
        h._pw = sync_playwright().start()
        h._browser = h._pw.chromium.launch()
        p = h._page = h._browser.new_page(viewport={"width": 1280, "height": 900})
        p.goto(f"{acme_odoo.URL}/web/login?db={h.db}")
        p.fill("input[name=login]", acme_odoo.USER)
        p.fill("input[name=password]", acme_odoo.PASSWORD)
        p.click("button[type=submit]")
        p.wait_for_selector(".o_main_navbar", timeout=120000)
        p.goto(acme_odoo.URL + START)
        p.wait_for_selector(".o_action_manager .o_list_view, .o_action_manager .o_kanban_view", timeout=120000)
        _settle(p)
    return h._page


def _settle(p):
    try:
        p.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001  a page that keeps a connection open is read as it is
        pass
    p.wait_for_timeout(500)


def _scan(p):
    return p.evaluate(SCAN)


def _view(p, limit=70):
    got = _scan(p)
    lines = [f'{x["kind"]} "{x["name"]}"' + (f' = "{x["value"]}"' if x["kind"] == "field" else "") for x in got["items"][:limit]]
    return f"PAGE: {got['title']}\n" + "\n".join(lines)


def _find(p, kinds, name):
    got = _scan(p)
    for x in got["items"]:
        if x["kind"] in kinds and x["name"] == name:            # exactly the name the rules read
            return p.locator(f'[data-hx="{x["i"]}"]')
    there = [x["name"] for x in got["items"] if x["kind"] in kinds][:25]
    raise ValueError(f"the page \"{got['title']}\" has no {' or '.join(kinds)} named {name!r}. Its {'s, '.join(kinds)}s are: "
                     + (", ".join(json.dumps(n, ensure_ascii=False) for n in there) or "none")
                     + ". If the one you need is not there, you are on another page: open the right one first")


def look(h):
    return _view(page(h))


def click(h, kind, name):
    p = page(h)
    el = _find(p, (kind,), name)
    if kind == "row":
        (el.locator("td.o_data_cell").first if el.locator("td.o_data_cell").count() else el).click()
    else:
        el.click()
    _settle(p)
    return _view(p)


def type_text(h, field, text, enter=False):
    p = page(h)
    el = _find(p, ("field",), field)
    el.fill(text)
    if enter:
        el.press("Enter")
    else:
        el.press("Tab")
    _settle(p)
    return _view(p)


def close(h):
    for name in ("_browser", "_pw"):
        obj = getattr(h, name, None)
        try:
            if obj is not None:
                (obj.close if name == "_browser" else obj.stop)()
        except Exception:  # noqa: BLE001
            pass
    h._page = h._browser = h._pw = None
