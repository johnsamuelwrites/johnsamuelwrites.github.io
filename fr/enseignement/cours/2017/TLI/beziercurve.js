var y = 0;
var x1 = 10;
var x2 = 210;
function courbebezieranimated() {
  var id = document.getElementById("courbebezieranimated");
  var context = id.getContext("2d");

  context.clearRect(0, 0, id.width, id.height);
  context.strokeStyle =  "#00b33c";
  context.lineWidth = 10;
  context.beginPath();
  context.moveTo(10,20);
  context.bezierCurveTo(x1, y, x2, y, 210, 20);
  context.stroke();

  context.fillStyle =  "black";
  context.lineWidth = 1;
  context.beginPath();
  context.arc(x1, y, 7, 0, 2 * Math.PI);
  context.fill();
  context.beginPath();
  context.arc(x2, y, 7, 0, 2 * Math.PI);
  context.fill();
  if(y>id.height-20) {
    x1++;
    x2--;
    if(x1 == x2) {
      y = 150;
      x1 = 10;
      x2 = 210;
    }
  }
  else {
    y++;
  }
  window.requestAnimationFrame(courbebezieranimated);
}

window.requestAnimationFrame(courbebezieranimated);
