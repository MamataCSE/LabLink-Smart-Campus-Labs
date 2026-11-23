const $ = (id) => document.getElementById(id);
let user = null, equipment = [];
const toast = (message, error=false) => { const el=$("toast"); el.textContent=message; el.className=error?"show error":"show"; clearTimeout(window.toastTimer); window.toastTimer=setTimeout(()=>el.className="",3800); };
async function api(url, options={}) {
  const response=await fetch(url,{headers:{"Content-Type":"application/json"},...options});
  const data=await response.json().catch(()=>({error:"Unexpected server response."}));
  if(!response.ok) { const err=new Error(data.error||"Request failed."); err.data=data; throw err; }
  return data;
}
const esc = s => String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmt(value){if(!value)return "—";return new Date(value).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});}
async function loadEquipment(){
  const params=new URLSearchParams({q:$("searchInput").value,department:$("departmentFilter").value,category:$("categoryFilter").value});
  equipment=await api("/api/equipment?"+params);
  const list=$("availableOnly").checked?equipment.filter(x=>x.available>0):equipment;
  $("resultCount").textContent=`${list.length} resources`;
  $("equipmentGrid").innerHTML=list.length?list.map(x=>`<article class="equipment-card"><div class="equipment-icon">${esc(x.image)}</div><h3>${esc(x.name)}</h3><p>${esc(x.department)} · ${esc(x.category)}</p><div class="equipment-meta">⌖ ${esc(x.location)}<br>▣ ${x.available} of ${x.total_units} available</div><div class="card-bottom"><span class="${x.available?'available':'available unavailable'}">${x.available?'● Available':'● Fully booked'}</span><button class="small-btn" data-detail="${x.id}">View details →</button></div></article>`).join(""):`<div class="empty">No equipment matches these filters. Try changing your search.</div>`;
  $("requestEquipment").innerHTML='<option value="">Choose equipment</option>'+equipment.map(x=>`<option value="${x.id}">${esc(x.name)} — ${esc(x.department)}</option>`).join("");
}
async function loadDashboard(){
  if(!user){$("stats").innerHTML='<div class="stat"><span>Equipment types</span><b>8</b></div><div class="stat"><span>Departments</span><b>3</b></div><div class="stat"><span>Sample resources</span><b>Ready</b></div><div class="stat"><span>AI matching</span><b>On</b></div>';return;}
  const d=await api("/api/dashboard");
  $("stats").innerHTML=`<div class="stat"><span>Equipment types</span><b>${d.total}</b></div><div class="stat"><span>Resources available now</span><b>${d.available}</b></div><div class="stat"><span>Upcoming bookings</span><b>${d.upcoming.length}</b></div><div class="stat"><span>${d.role==="faculty"?"Pending approvals":"My requests"}</span><b>${d.role==="faculty"?d.pending.length:d.requests.filter(x=>x.status==="Pending").length}</b></div>`;
  const upcoming=d.upcoming.length?d.upcoming.map(x=>`<div class="list-row"><div><b>${esc(x.equipment_name)}</b><small>${fmt(x.start_at)} – ${fmt(x.end_at)}</small></div><span class="status Confirmed">Confirmed</span></div>`).join(""):'<div class="empty">No upcoming bookings yet.</div>';
  let second;
  if(d.role==="faculty"){
    $("facultySection").hidden=false;
    second=d.pending.length?d.pending.map(x=>`<div class="list-row"><div><b>${esc(x.project_name)}</b><small>${esc(x.student_name)} · ${esc(x.equipment_name)} · Deadline ${esc(x.deadline)}</small></div><span class="status">Pending</span></div>`).join(""):'<div class="empty">No pending requests.</div>';
    $("facultyRequests").innerHTML=d.pending.length?d.pending.map(x=>`<div class="list-row"><div><b>${esc(x.project_name)}</b><small>${esc(x.student_name)} · ${esc(x.equipment_name)}<br>Deadline: ${esc(x.deadline)}<br>${esc(x.purpose)}</small></div><div class="faculty-actions"><button class="small-btn" data-decision="Approved" data-id="${x.id}">Approve</button><button class="small-btn" data-decision="Rejected" data-id="${x.id}">Reject</button></div></div>`).join(""):'<div class="empty">All caught up. No pending project requests.</div>';
  }else{
    $("facultySection").hidden=true;
    second=d.requests.length?d.requests.map(x=>`<div class="list-row"><div><b>${esc(x.project_name)}</b><small>${esc(x.equipment_name)} · ${esc(x.deadline)}</small></div><span class="status ${esc(x.status)}">${esc(x.status)}</span></div>`).join(""):'<div class="empty">You have not submitted a project request yet.</div>';
  }
  $("dashboardContent").innerHTML=`<div class="panel"><h3>Upcoming bookings</h3>${upcoming}</div><div class="panel"><h3>${d.role==="faculty"?"Recent pending requests":"My project requests"}</h3>${second}</div>`;
}
async function refreshUser(){
  const d=await api("/api/me");user=d.user;
document.body.classList.toggle("logged-in",!!user);
  $("userLabel").textContent=user?`${user.name} · ${user.role}`:"Guest";
  $("logoutBtn").hidden=!user;$("loginPanel").hidden=!!user;
  await loadDashboard();
}
$("loginForm").addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/login",{method:"POST",body:JSON.stringify({email:$("email").value,password:$("password").value})});await refreshUser();toast("Welcome to LabLink.");}catch(err){toast(err.message,true);}});
$("logoutBtn").addEventListener("click",async()=>{await api("/api/logout",{method:"POST"});await refreshUser();toast("Signed out.");});
["searchInput","departmentFilter","categoryFilter","availableOnly"].forEach(id=>$(id).addEventListener(id==="searchInput"?"input":"change",()=>loadEquipment().catch(e=>toast(e.message,true))));
$("equipmentGrid").addEventListener("click",e=>{const b=e.target.closest("[data-detail]");if(b)showDetails(Number(b.dataset.detail));});
async function showDetails(id){
  try{const x=await api(`/api/equipment/${id}`);$("detailName").textContent=x.name;
  $("detailBody").innerHTML=`<p class="muted">${esc(x.department)} · ${esc(x.category)} · ${esc(x.location)}</p><div class="detail-spec"><b>Specifications</b><br>${esc(x.specs)}<br><br><b>Availability</b><br>${x.available} of ${x.total_units} units currently available</div><h3>Current bookings</h3><div class="booking-list">${x.bookings.length?x.bookings.map(b=>`${fmt(b.start_at)} – ${fmt(b.end_at)} · ${esc(b.name)}`).join("<br>"):"No bookings recorded."}</div>${user?.role==="student"?`<form id="bookingForm" class="booking-form"><label>Start time<input type="datetime-local" id="bookStart" required></label><label>End time<input type="datetime-local" id="bookEnd" required></label><button class="btn btn-primary">Book this equipment</button></form>`:'<p class="muted">Sign in as a student to book a slot.</p>'}`;
  $("detailDialog").showModal();
  const f=$("bookingForm");if(f)f.addEventListener("submit",async e=>{e.preventDefault();try{await api("/api/bookings",{method:"POST",body:JSON.stringify({equipment_id:id,start_at:$("bookStart").value,end_at:$("bookEnd").value})});$("detailDialog").close();toast("Booking confirmed.");await loadEquipment();await loadDashboard();}catch(err){let msg=err.message;if(err.data?.alternatives?.length)msg+=" Suggested: "+err.data.alternatives.map(a=>fmt(a.start_at)).join(", ");if(err.data?.alternative_equipment?.length)msg+=" Other options: "+err.data.alternative_equipment.map(a=>a.name).join(", ");toast(msg,true);}});
  }catch(e){toast(e.message,true);}
}
$("closeDialog").addEventListener("click",()=>$("detailDialog").close());
$("requestForm").addEventListener("submit",async e=>{e.preventDefault();if(!user){toast("Please sign in as a student first.",true);return;}try{const result=await api("/api/requests",{method:"POST",body:JSON.stringify({project_name:$("projectName").value,deadline:$("deadline").value,equipment_id:$("requestEquipment").value,purpose:$("purpose").value})});toast(result.message);$("requestForm").reset();await loadDashboard();}catch(err){toast(err.message,true);}});
$("recommendBtn").addEventListener("click",async()=>{if(!user){toast("Sign in to get project recommendations.",true);return;}const box=$("recommendations");box.hidden=false;box.innerHTML="<div class='empty'>Finding suitable lab resources…</div>";try{const d=await api("/api/recommend",{method:"POST",body:JSON.stringify({project_name:$("projectName").value,purpose:$("purpose").value,deadline:$("deadline").value})});box.innerHTML=`<h4>✦ ${esc(d.mode)} recommendations</h4><p class="muted">${esc(d.summary)}</p>`+d.recommendations.map(x=>`<div class="recommendation"><b>${esc(x.name)}</b> · ${x.available} available<small>${esc(x.department)} · ${esc(x.location)}<br>${esc(x.reason)}</small><button class="small-btn" data-pick="${x.id}">Use this equipment</button></div>`).join("");}catch(e){box.innerHTML="";toast(e.message,true);}});
$("recommendations").addEventListener("click",e=>{const b=e.target.closest("[data-pick]");if(b){$("requestEquipment").value=b.dataset.pick;toast("Equipment selected in your request form.");}});
$("facultyRequests").addEventListener("click",async e=>{const b=e.target.closest("[data-decision]");if(!b)return;b.disabled=true;try{const d=await api(`/api/requests/${b.dataset.id}/decision`,{method:"POST",body:JSON.stringify({decision:b.dataset.decision})});toast(d.message);await loadDashboard();}catch(err){toast(err.message,true);b.disabled=false;}});
$("deadline").min=new Date().toISOString().slice(0,10);
(async()=>{try{await loadEquipment();await refreshUser();}catch(e){toast("Could not connect to LabLink. Refresh the page.",true);}})();
